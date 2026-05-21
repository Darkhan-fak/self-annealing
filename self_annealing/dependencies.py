import importlib.metadata
import os
import pathlib
import platform
import re
import sys

try:
    from packaging.version import Version as PackagingVersion
    from packaging.specifiers import SpecifierSet
    USE_PACKAGING = True
except ImportError:
    USE_PACKAGING = False

try:
    from packaging.markers import Marker
    USE_MARKERS = True
except ImportError:
    USE_MARKERS = False

def normalize_name(name: str) -> str:
    """Normalize a package name according to PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()

def get_installed_version(package_name: str) -> str:
    """
    Get the installed version of a package.
    Attempts direct lookup, normalized lookup, and distribution scanning.
    """
    # Direct lookup
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        pass
    
    norm_target = normalize_name(package_name)
    # Normalized lookup
    try:
        return importlib.metadata.version(norm_target)
    except importlib.metadata.PackageNotFoundError:
        pass

    # Scanning distributions
    try:
        for dist in importlib.metadata.distributions():
            dist_name = dist.metadata.get("Name") or getattr(dist, "name", None)
            if dist_name and normalize_name(dist_name) == norm_target:
                return dist.version
    except Exception:
        pass
    
    return None

def clean_version_str(ver_str: str) -> str:
    """Remove leading 'v' or 'V' from version string if it's followed by a digit."""
    ver_str = ver_str.strip()
    if (ver_str.startswith('v') or ver_str.startswith('V')) and len(ver_str) > 1 and ver_str[1].isdigit():
        ver_str = ver_str[1:]
    return ver_str

def parse_version_tuple(version_str: str) -> tuple:
    """
    Parses a version string like '1.2.3' or '0.4.6' into a tuple of ints/strs for comparison.
    E.g. '1.2.3-rc1' -> (1, 2, 3, 'rc1')
    """
    version_str = clean_version_str(version_str)
    parts = re.split(r'[.-]', version_str)
    result = []
    for p in parts:
        p = p.strip()
        if p.isdigit():
            result.append(int(p))
        elif p:
            match = re.match(r'^(\d+)(.*)$', p)
            if match:
                result.append(int(match.group(1)))
                if match.group(2):
                    result.append(match.group(2))
            else:
                result.append(p)
    return tuple(result)

def compare_versions(v1_str: str, op: str, v2_str: str) -> bool:
    """Compare two version strings using a fallback comparison algorithm."""
    t1 = parse_version_tuple(v1_str)
    t2 = parse_version_tuple(v2_str)
    
    max_len = max(len(t1), len(t2))
    t1_padded = t1 + (0,) * (max_len - len(t1))
    t2_padded = t2 + (0,) * (max_len - len(t2))
    
    def compare_elements(e1, e2):
        if type(e1) == type(e2):
            return (e1 > e2) - (e1 < e2)
        return (str(e1) > str(e2)) - (str(e1) < str(e2))

    comparison_res = 0
    for e1, e2 in zip(t1_padded, t2_padded):
        res = compare_elements(e1, e2)
        if res != 0:
            comparison_res = res
            break
            
    if op == "==":
        return comparison_res == 0
    elif op == "!=":
        return comparison_res != 0
    elif op == ">=":
        return comparison_res >= 0
    elif op == "<=":
        return comparison_res <= 0
    elif op == ">":
        return comparison_res > 0
    elif op == "<":
        return comparison_res < 0
    elif op == "~=":
        if comparison_res < 0:
            return False
        if len(t2) >= 2:
            t2_limit = list(t2[:-1])
            try:
                t2_limit[-1] += 1
            except TypeError:
                return True
            t2_limit_tuple = tuple(t2_limit)
            max_l = max(len(t1), len(t2_limit_tuple))
            t1_p = t1 + (0,) * (max_l - len(t1))
            t2_lim_p = t2_limit_tuple + (0,) * (max_l - len(t2_limit_tuple))
            
            comp_limit = 0
            for e1, e2 in zip(t1_p, t2_lim_p):
                res = compare_elements(e1, e2)
                if res != 0:
                    comp_limit = res
                    break
            return comp_limit < 0
        else:
            try:
                return t1[0] < t2[0] + 1
            except TypeError:
                return True
    elif op == "===":
        return v1_str == v2_str
    return False

def evaluate_marker_fallback(marker_str: str) -> bool:
    """Evaluate simple PEP 508 markers without packaging library."""
    if not marker_str:
        return True
    
    # Standard environments dict
    version_parts = platform.python_version_tuple()
    env = {
        "python_version": f"{version_parts[0]}.{version_parts[1]}",
        "python_full_version": platform.python_version(),
        "sys_platform": sys.platform,
        "os_name": os.name,
        "platform_system": platform.system(),
        "implementation_name": sys.implementation.name,
    }
    
    marker_str = marker_str.replace("'", '"')
    
    def eval_expr(expr: str) -> bool:
        expr = expr.strip()
        pattern = r'([a-zA-Z0-9_]+)\s*(==|!=|>=|<=|>|<|in|not\s+in)\s*"([^"]*)"'
        match = re.match(pattern, expr)
        if not match:
            pattern_no_quotes = r'([a-zA-Z0-9_]+)\s*(==|!=|>=|<=|>|<|in|not\s+in)\s*([a-zA-Z0-9_.-]+)'
            match = re.match(pattern_no_quotes, expr)
            if not match:
                return True
            
        var, op, val = match.groups()
        if var not in env:
            if var == "extra":
                return False
            return True
            
        actual_val = env[var]
        
        if op == "==":
            return actual_val == val
        elif op == "!=":
            return actual_val != val
        elif op == ">=":
            return compare_versions(actual_val, ">=", val)
        elif op == "<=":
            return compare_versions(actual_val, "<=", val)
        elif op == ">":
            return compare_versions(actual_val, ">", val)
        elif op == "<":
            return compare_versions(actual_val, "<", val)
        elif op == "in":
            return actual_val in val
        elif op == "not in":
            return actual_val not in val
        return True

    if " or " in marker_str:
        parts = marker_str.split(" or ")
        return any(eval_expr(p) for p in parts)
    elif " and " in marker_str:
        parts = marker_str.split(" and ")
        return all(eval_expr(p) for p in parts)
    else:
        return eval_expr(marker_str)

def parse_dependency_specifier(dep_str: str) -> tuple[str, list[tuple[str, str]], str]:
    """
    Parses a PEP 508 dependency string.
    Returns: (package_name, list of (operator, version_str), marker_str)
    """
    marker_str = ""
    if ";" in dep_str:
        dep_str, marker_str = dep_str.split(";", 1)
        marker_str = marker_str.strip()
    
    dep_str = dep_str.strip()
    match = re.match(r"^([a-zA-Z0-9-_.]+)(?:\[[^\]]+\])?", dep_str)
    if not match:
        return "", [], marker_str
    
    package_name = match.group(1)
    specifiers_part = dep_str[match.end():].strip()
    
    specifiers = []
    if specifiers_part:
        if specifiers_part.startswith("@"):
            specifiers.append(("@", specifiers_part[1:].strip()))
        else:
            pattern = r"\s*(~=|==|!=|<=|>=|<|>|===)\s*([a-zA-Z0-9-_.]+)"
            matches = re.findall(pattern, specifiers_part)
            for op, ver in matches:
                specifiers.append((op, ver.strip()))
            
    return package_name, specifiers, marker_str

def parse_requirements_txt(content: str) -> list[str]:
    """Parse dependencies from requirements.txt content."""
    dependencies = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            continue
        # Strip pip-specific options starting with " --"
        if " --" in line:
            line = line.split(" --", 1)[0].strip()
        parts = re.split(r"\s+#", line, maxsplit=1)
        line = parts[0].strip()
        if line:
            dependencies.append(line)
    return dependencies

def parse_pyproject_toml(content: str) -> list[str]:
    """Parse project dependencies from pyproject.toml content."""
    try:
        import tomllib
        data = tomllib.loads(content)
        return data.get("project", {}).get("dependencies", [])
    except ImportError:
        try:
            import tomli
            data = tomli.loads(content)
            return data.get("project", {}).get("dependencies", [])
        except ImportError:
            pass
            
    dependencies = []
    in_project = False
    in_dependencies = False
    dep_block = []
    
    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith("[") and line_clean.endswith("]"):
            header = line_clean[1:-1].strip()
            if header == "project":
                in_project = True
            else:
                in_project = False
                in_dependencies = False
            continue
        
        if in_project:
            if not in_dependencies and re.match(r"^dependencies\s*=\s*\[", line_clean):
                in_dependencies = True
                rest = line_clean.split("[", 1)[1]
                if "]" in rest:
                    content_inside = rest.split("]", 1)[0]
                    dep_block.append(content_inside)
                    in_dependencies = False
                else:
                    dep_block.append(rest)
                continue
            
            if in_dependencies:
                if "]" in line_clean:
                    rest = line_clean.split("]", 1)[0]
                    dep_block.append(rest)
                    in_dependencies = False
                else:
                    dep_block.append(line_clean)
                    
    full_block = "".join(dep_block)
    raw_deps = re.findall(r'["\']([^"\']+)["\']', full_block)
    return raw_deps

def check_dependencies(project_dir: str) -> list[str]:
    """
    Check if dependencies declared in requirements.txt or pyproject.toml
    under project_dir are installed and have matching versions.
    """
    project_path = pathlib.Path(project_dir)
    requirements_file = project_path / "requirements.txt"
    pyproject_file = project_path / "pyproject.toml"
    
    errors = []
    
    if not requirements_file.is_file() and not pyproject_file.is_file():
        return [f"No requirements.txt or pyproject.toml found in {project_dir}"]
        
    declared_deps = []
    
    if requirements_file.is_file():
        try:
            content = requirements_file.read_text(encoding="utf-8")
            declared_deps.extend(parse_requirements_txt(content))
        except Exception as e:
            errors.append(f"Failed to read requirements.txt: {e}")
            
    if pyproject_file.is_file():
        try:
            content = pyproject_file.read_text(encoding="utf-8")
            declared_deps.extend(parse_pyproject_toml(content))
        except Exception as e:
            errors.append(f"Failed to read pyproject.toml: {e}")
            
    for dep_str in declared_deps:
        dep_str = dep_str.strip()
        if not dep_str:
            continue
            
        package_name, specifiers, marker_str = parse_dependency_specifier(dep_str)
        if not package_name:
            continue
            
        if marker_str:
            if USE_MARKERS:
                try:
                    from packaging.markers import Marker
                    marker_applies = Marker(marker_str).evaluate()
                except Exception:
                    marker_applies = evaluate_marker_fallback(marker_str)
            else:
                marker_applies = evaluate_marker_fallback(marker_str)
                
            if not marker_applies:
                continue
                
        installed_ver = get_installed_version(package_name)
        if installed_ver is None:
            errors.append(f"Package '{package_name}' is declared but not installed.")
            continue
            
        specifiers_clean = []
        is_direct_ref = False
        for op, ver in specifiers:
            if op == "@" or ver.startswith("http") or ver.startswith("file"):
                is_direct_ref = True
                break
            specifiers_clean.append((op, ver))
            
        if is_direct_ref:
            continue
            
        if specifiers_clean:
            if USE_PACKAGING:
                spec_str = ",".join(f"{op}{ver}" for op, ver in specifiers_clean)
                try:
                    specset = SpecifierSet(spec_str)
                    is_match = PackagingVersion(installed_ver) in specset
                except Exception:
                    is_match = False
                    
                if not is_match:
                    errors.append(
                        f"Package '{package_name}' version mismatch: "
                        f"installed '{installed_ver}', but require '{spec_str}'."
                    )
            else:
                mismatched = []
                for op, ver in specifiers_clean:
                    if not compare_versions(installed_ver, op, ver):
                        mismatched.append(f"{op}{ver}")
                if mismatched:
                    spec_str = ",".join(f"{op}{ver}" for op, ver in specifiers_clean)
                    errors.append(
                        f"Package '{package_name}' version mismatch: "
                        f"installed '{installed_ver}', but require '{spec_str}'."
                    )
                    
    return errors
