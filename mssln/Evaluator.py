import re

import os.path

class Environment:
    def __init__(self,initial_vars=None,initial_meta=None):
        if initial_vars is not None:
            self.vars = dict(initial_vars)
        else:
            self.vars = {}

        if initial_meta is not None:
            self.meta = dict(initial_meta)
        else:
            self.meta = {}

    def set_var(self,name,value):
        print "setting %s = %s" % (name,value)
        self.vars[name] = value

    def get_var(self,name):
        if self.vars.has_key(name):
            return self.vars[name]
        else:
            return self.get_undefined_var(name)

    def get_undefined_var(self,name):
        print "warning: access to undefined variable (%s)" % (name)
        return ""

    def set_meta_var(self,name,value):
        print "setting meta %s = %s" % (name,value)
        self.meta[name] = value

    def get_meta_var(self,name):
        if self.meta.has_key(name):
            return self.meta[name]
        else:
            return self.get_undefined_meta(name)

    def get_undefined_meta(self,name):
        print "warning: access to undefined meta variable (%s)" % (name)
        return ""

def _eval_subst_vars(expr,env):
    result      = expr
    start       = 0
    start_index = result.find("$(")

    while start_index >= 0:
        end_index = result.find(")",start_index + 2)

        if end_index >= 0:
            value = str(env.get_var(result[start_index + 2:end_index]))

            result      = result[:start_index] + value + result[end_index + 1:]
            start_index = result.find("$(",start_index + len(value))
        else:
            raise RunTimeException("unterminated variable reference in '%s'" % (expr))

    return result

def _eval_subst_meta_vars(expr,env):
    result      = expr
    start       = 0
    start_index = result.find("%(")

    while start_index >= 0:
        end_index = result.find(")",start_index + 2)

        if end_index >= 0:
            value = str(env.get_meta_var(result[start_index + 2:end_index]))

            result      = result[:start_index] + value + result[end_index + 1:]
            start_index = result.find("%(",start_index + len(value))
        else:
            raise RunTimeException("unterminated meta variable reference in '%s'" % (expr))

    return result

def _eval_subst_home_envvar(expr):
    parts = expr.split("$HOME")

    if len(parts) > 1:
        return os.environ['HOME'].join(parts)
    else:
        return expr

def _eval_substitute_vars(expr,env):
    result = _eval_subst_vars(expr,env)
    result = _eval_subst_meta_vars(result,env)
    result = _eval_subst_home_envvar(result)
    return result

def _eval_special_cases(expr,env):
    m = re.match("\$\(([a-zA-Z]+?)\.EndsWith\(('[^']*?)'\)\)",expr)

    if m is not None:
        varname = m.group(1)
        suffix  = m.group(2)

        value = env.get_var(varname)

        return value.endswith(suffix)

    m = re.match("\$\(\[System.IO.Path\]::GetDirectoryName\(\$\(([a-zA-Z]+?)\)\)\)",expr)

    if m is not None:
        varname = m.group(1)

        value = env.get_var(varname)

        return os.path.dirname(value)
    else:
        return _eval_substitute_vars(expr,env)

def _eval_primary(expr,env):
    return _eval_special_cases(expr,env)

def _eval_comparison(expr,env):
    m = re.match("'([^']*?)'=='([^']*)'",expr)

    if m is not None:
        left  = _eval_expr(m.group(1),env)
        right = _eval_expr(m.group(2),env)

        return left == right
    else:
       return _eval_primary(expr,env)

def _eval_expr(expr,env):
    return _eval_comparison(expr,env)

def evaluate_expression(expr,env):
    return _eval_expr(expr,env)

def substitute_vars(value,env):
    return _eval_substitute_vars(value,env)

