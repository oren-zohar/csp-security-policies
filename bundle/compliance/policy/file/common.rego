package compliance.policy.file.common

import data.compliance.lib.assert

file_ownership_match(user, group, required_user, required_group) {
	user == required_user
	group == required_group
} else = false {
	true
}

file_permission_match(filemode, user, group, other) {
	permissions = parse_permission(filemode)

	# filemode format {user}{group}{other} e.g. 644
	check_permissions(permissions, [user, group, other])
} else = false {
	true
}

file_permission_match_exact(filemode, user, group, other) {
	permissions = parse_permission(filemode)

	# filemode format {user}{group}{other} e.g. 644
	permissions == [user, group, other]
} else = false {
	true
}

# return a list of file premission [user, group, other]
parse_permission(filemode) = permissions {
	# cast to numbers
	permissions := [to_number(p) | p = split(filemode, "")[_]]
}

check_permissions(permissions, max_permissions) {
	assert.all_true([r | r = bits.and(permissions[p], bits.negate(max_permissions[p])) == 0])
} else = false {
	true
}

# check if file is in path
file_in_path(path, file_path) {
	closed_path := concat("", [file_path, "/"]) # make sure last dir name is closed by "/"
	contains(closed_path, path)
} else = false {
	true
}
