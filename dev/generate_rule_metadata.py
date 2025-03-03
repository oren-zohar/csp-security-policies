import argparse
import os
import uuid

import pandas as pd

import common
from dataclasses import dataclass, asdict

from ruamel.yaml import YAML

yml = YAML()


@dataclass
class Benchmark:
    name: str
    version: str
    id: str


@dataclass
class Rule:
    id: str
    name: str
    rule_number: str
    profile_applicability: str
    description: str
    rationale: str
    audit: str
    remediation: str
    impact: str
    default_value: str
    references: str
    section: str
    version: str
    tags: list[str]
    benchmark: Benchmark


selected_columns_map = {
    "cis_k8s": {
        "Section #": "Section",
        "Recommendation #": "Rule Number",
        "Title": "Title",
        "Description": "description",
        "Rational Statement": "rationale",
        "Audit Procedure": "audit",
        "Remediation Procedure": "remediation",
        "Impact Statement": "impact",
        # "": "default_value", # todo: talk with CIS team to add this column to the excel
        "references": "references",
        "Assessment Status": "type",
    },
    "cis_eks": {
        "section #": "Section",
        "recommendation #": "Rule Number",
        "title": "Title",
        "description": "description",
        "rationale statement": "rationale",
        "audit procedure": "audit",
        "remediation procedure": "remediation",
        "impact statement": "impact",
        # "": "default_value", # todo: talk with CIS team to add this column to the excel
        "references": "references",
        "scoring status": "type",
    },
    "cis_aws": {
        "Section #": "Section",
        "Recommendation #": "Rule Number",
        "Title": "Title",
        "Description": "description",
        "Rational Statement": "rationale",
        "Audit Procedure": "audit",
        "Remediation Procedure": "remediation",
        "Impact Statement": "impact",
        # "": "default_value", # todo: talk with CIS team to add this column to the excel
        "References": "references",
        "Assessment Status": "type",
    }
}


def parse_refs(refs: str):
    """
    Parse references - they are split by `:` which is the worst token possible for urls...
    """
    ref = [f"http{ref}" for ref in refs.split(":http") if ref]
    ref[0] = ref[0].removeprefix("http")
    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(ref))


def read_existing_default_value(rule_number, benchmark_id):
    """
    Read default value from existing rule (The excel file doesn't contain default values)
    :param rule_number: Rule number
    :param benchmark_id: Benchmark ID
    :return: Default value
    """
    rule_dir = os.path.join(common.rules_dir, f"{benchmark_id}/rules", f"cis_{rule_number.replace('.', '_')}")
    try:
        with open(os.path.join(rule_dir, "data.yaml"), "r") as f:
            default_value = yml.load(f)["metadata"]["default_value"]
            return default_value
    except FileNotFoundError:
        print(f"{benchmark_id}/{rule_number} is missing default value - please make sure to add it manually")
        return ""


def generate_metadata(benchmark_id: str, raw_data: pd.DataFrame, benchmark_metadata: Benchmark, sections: dict):
    """
    Generate metadata for rules
    :param benchmark_id: Benchmark ID
    :param raw_data: ‘Raw’ data from the spreadsheet
    :param benchmark_metadata: Benchmark metadata
    :param sections: Section metadata
    :return: List of Rule objects
    """
    metadata = []
    benchmark_tag = benchmark_id.removesuffix("cis_").upper() if benchmark_id != "cis_k8s" else f"Kubernetes"
    for rule in raw_data.to_dict(orient="records"):
        r = Rule(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{benchmark_metadata.name} {rule['Title']}")),
            name=rule["Title"],
            rule_number=rule["Rule Number"],
            profile_applicability=f"* {rule['profile_applicability']}",
            description=common.fix_code_blocks(rule["description"]),
            rationale=common.fix_code_blocks(rule.get("rationale", "")),
            audit=common.fix_code_blocks(rule.get("audit", "")),
            remediation=common.fix_code_blocks(rule.get("remediation", "")),
            impact=rule.get("impact", "") if rule.get("impact", "") != "nan" else "None",
            default_value=rule.get("default_value", read_existing_default_value(rule["Rule Number"], benchmark_id)),
            references=parse_refs(rule.get("references", "")),
            section=sections[rule["Section"]],
            tags=["CIS", benchmark_tag, f"CIS {rule['Rule Number']}", sections[rule["Section"]]],
            version="1.0",
            benchmark=benchmark_metadata,
        )
        metadata.append(r)

    return metadata


def save_metadata(metadata: list[Rule], benchmark_id):
    """
    Save metadata to file
    :param metadata: List of Rule objects
    :param benchmark_id: Benchmark ID
    :return: None
    """
    for rule in metadata:
        rule_dir = os.path.join(common.rules_dir, f"{benchmark_id}/rules", f"cis_{rule.rule_number.replace('.', '_')}")
        try:
            with open(os.path.join(rule_dir, "data.yaml"), "w+") as f:
                yml.dump({"metadata": common.apply_pss_recursively(asdict(rule))}, f)

        except FileNotFoundError:
            continue  # ignore rules that are not implemented


if __name__ == "__main__":
    os.chdir(common.repo_root.working_dir + "/dev")

    parser = argparse.ArgumentParser(
        description="CIS Benchmark parser CLI",
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        default=common.benchmark.keys(),
        choices=common.benchmark.keys(),
        help="benchmark to be used for the rules metadata generation (default: all benchmarks). "
             "for example: `--benchmark cis_eks` or `--benchmark cis_eks cis_aws`",
        nargs="+",
    )
    parser.add_argument(
        "-r",
        "--rules",
        help="set of specific rules to be parsed (default: all rules).",
        nargs="+",
    )
    args = parser.parse_args()

    if type(args.benchmark) is str:
        args.benchmark = [args.benchmark]

    for benchmark_id in args.benchmark:
        print(f"### Processing {benchmark_id.replace('_', ' ').upper()}")

        # Parse Excel data
        raw_data, sections = common.parse_rules_data_from_excel(
            selected_columns=selected_columns_map,
            benchmark_id=benchmark_id,
            selected_rules=args.rules,
        )

        benchmark_metadata = Benchmark(
            name=common.benchmark[benchmark_id].split("Benchmark")[0].replace("_", " ").removesuffix(" "),
            version=common.benchmark[benchmark_id].split("Benchmark")[1].removeprefix("_").removesuffix(".xlsx"),
            id=f"{benchmark_id}",
        )
        metadata = generate_metadata(benchmark_id, raw_data, benchmark_metadata, sections)
        save_metadata(metadata, benchmark_id)
