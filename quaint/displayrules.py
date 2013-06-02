
from types import FunctionType, MethodType
from descr import descr, HTMLRuleBuilder as RB
from .parser import ASTNode

def ugdescr(x, recurse = None):
    v = descr(x, ugdescr)
    if isinstance(x, ASTNode):
        if hasattr(x, "location"):
            return [{"$located"}] + list(v)
        else:
            return [{"!located"}] + list(v)
    else:
        return v

def minimal_rules():
    rules = RB()
    rules.css_border(".{!located}", "4px solid red")
    return rules

def pretty_rules():
    rules = RB()

    # Scalars and identifiers
    rules.pmclasses(".{@ASTNode} .{@str}", "identifier", {"@str", "scalar"})
    rules.css_padding(".identifier, .{@int}, .{$lib}", "4px")
    rules.css_color(".{$lib}", "#8f8")

    # Operators and juxtaposition
    for cls, color in [(".{+oper}", "#ff8"),
                       (".{+juxt}", "#fff"),
                       (".{+send}", "#fff")]:
        rules.mclasses(cls, "object")
        rules.css_border_bottom(".{+oper}" + " > * > " + cls, "2px solid " + color)
        rules.css_border_bottom(".{+juxt}" + " > * > " + cls, "2px solid " + color)
        rules.css_border_bottom(".{+send}" + " > * > " + cls, "2px solid " + color)
        rules.css_margin(cls, "6px")

    def rearrange_oper(classes, children):
        op = children[0]
        results = [children[1]]
        for child in children[2:]:
            results += [[{"operator"}, op], child]
        return results

    rules.css_color(".operator", "#ff8")
    rules.rearrange(".{+oper}", rearrange_oper)


    for cls, color in [(".{+bracket}", "#f80"),
                       (".{+block}", "#08f")]:

        rules.builder_for(cls) \
            .mclasses("object") \
            .css_background_color(color) \
            .css_margin("4px") \
            .css_padding("4px") \
            .css_border_radius("5px")

        rules.builder_for(cls + " > *") \
            .css_background_color("#000") \
            .css_margin_left("2px") \
            .css_margin_right("2px") \
            .css_border_radius("5px")

        rules.builder_for(cls + " > :first-child") \
            .css_background_color(color) \
            .css_color("#000") \
            .css_font_weight("bold")


    # # Boxes
    # for cls, color in [(".{+square}", "#f80"),
    #                    (".{+curly}", "#0a0"),
    #                    (".{+begin}", "#08f"),
    #                    (".{+seq}", "#f80")]:

    #     rules.builder_for(cls) \
    #         .mclasses("object") \
    #         .css_background_color(color) \
    #         .css_margin("4px") \
    #         .css_padding("4px") \
    #         .css_border_radius("5px")

    #     rules.builder_for(cls + " > *") \
    #         .css_background_color("#000") \
    #         .css_margin_left("2px") \
    #         .css_margin_right("2px") \
    #         .css_border_radius("5px")

    rules.css_margin_top(".{+block} > *", "6px")
    rules.css_margin_bottom(".{+block} > *", "6px")

    # Begin
    rules.css_display(".{+block} > *", "block")

    # rules.hide(".{+void}")

    rules.mclasses(".{+void}", "object")
    rules.pclasses(".{+void}", "identifier")
    rules.rearrange(".{+void}", lambda classes, contents: "\u2205")
    rules.css_color(".{+void}", "#888")

    return rules


rules = minimal_rules() + pretty_rules()
