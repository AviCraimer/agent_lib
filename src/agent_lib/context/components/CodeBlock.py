import re
from agent_lib.context.CtxComponent import CtxComponent
from agent_lib.context.Props import Props, propsclass
from typing import Literal

# fmt: off
# This list is based on highlight.js
CodeblockLanguage = Literal[
    "1c", "4d", "abap", "abc", "abnf", "accesslog", "actionscript",
    "ada", "aiken", "ln", "alan", "angelscript", "apache", "apex",
    "applescript", "arcade", "arduino", "armasm", "asciidoc",
    "aspectj", "autohotkey", "autoit", "avrasm", "awk", "ballerina",
    "bash", "basic", "bbcode", "bicep", "blade", "bnf", "bqn",
    "brainfuck", "c", "csharp", "cpp", "cal", "c3", "cos", "candid",
    "capnproto", "chaos", "chapel", "cisco", "clojure", "cmake",
    "cobol", "codeowners", "coffeescript", "coq", "cpc", "crmsh",
    "crystal", "csp", "css", "curl", "cypher", "d", "dafny", "dart",
    "pascal", "diff", "django", "dns", "dockerfile", "dos",
    "dsconfig", "dts", "dust", "dylan", "ebnf", "elixir", "elm",
    "erlang", "excel", "extempore", "fsharp", "fix", "flix",
    "fortran", "func", "gcode", "gams", "gauss", "gdscript",
    "gherkin", "gleam", "glimmer", "gn", "go", "golo", "gradle",
    "gf", "graphql", "groovy", "gsql", "haml", "handlebars",
    "haskell", "haxe", "hlsl", "html", "http", "hy", "inform7",
    "ini", "toml", "iptables", "irpf90", "java", "javascript", "jsx", "jolie",
    "json", "jsonata", "julia", "julia-repl", "kotlin", "l4",
    "lang", "lasso", "tex", "ldif", "leaf", "lean", "less", "liquid",
    "lisp", "livecodeserver", "livescript", "lookml", "lua", "luau",
    "macaulay2", "magik", "makefile", "markdown", "mathematica",
    "matlab", "maxima", "mel", "mercury", "metapost", "mint",
    "mips", "mirc", "mirth", "mizar", "mkb", "mlir", "mojolicious",
    "monkey", "moonscript", "motoko", "n1ql", "never", "nginx",
    "nim", "nix", "nsis", "oak", "ocl", "objectivec", "ocaml",
    "odin", "glsl", "openscad", "ruleslanguage", "oxygene",
    "papyrus", "parser3", "perl", "pf", "phix", "php", "pinescript",
    "plaintext", "pony", "postgresql", "poweron", "powershell",
    "prisma", "processing", "prolog", "properties", "protobuf",
    "puppet", "python", "profile", "python-repl", "kdb", "qsharp",
    "qml", "r", "raku", "rakudoc", "rakuquoting", "rakuregexe",
    "cshtml", "reasonml", "redbol", "rib", "rsl", "rescript",
    "riscv", "riscript", "graph", "robot", "rpm-specfile", "ruby",
    "rust", "rvt-script", "sas", "scala", "scheme", "scilab", "scss",
    "sfz", "shexc", "shell", "smali", "smalltalk", "sml",
    "solidity", "spl", "sql", "stan", "stata", "step", "structured-text",
    "stylus", "subunit", "supercollider", "svelte", "swift", "tcl",
    "terraform", "tap", "thrift", "toit", "tp", "tsql", "ttcn3",
    "twig", "typescript", "tsx", "unicorn-rails-log", "unison", "vala",
    "vbnet", "vba", "vbscript", "verilog", "vhdl", "vim",
    "voltscript", "wgsl", "xsharp", "axapta", "x86asm", "x86asmatt",
    "xl", "xquery", "yaml", "zenscript", "zephir", "zig"
]
# fmt: on


@propsclass
class CodeBlockProps(Props):
    language: CodeblockLanguage


class CodeBlock(CtxComponent[CodeBlockProps]):
    _PropsClass = CodeBlockProps

    def __init__(self):

        def render_fn(props: CodeBlockProps):

            code = CodeBlock.strip_code_block(
                CtxComponent.render_children(props.children, "")
            )

            return f"```{props.language}\n{code}\n```"

        self._render_fn = render_fn

    @staticmethod
    def strip_code_block(code: str) -> str:
        """Strip existing code block fences if present."""
        stripped = code.strip()

        pattern = r"^```[a-zA-Z0-9]*\n(.*)\n```$"
        match = re.match(pattern, stripped, re.DOTALL)

        if match:
            return match.group(1)

        return code


MarkdownBlock = CodeBlock().preset(CodeBlockProps(language="markdown"))

JavascriptBlock = CodeBlock().preset(CodeBlockProps(language="javascript"))

TypescriptBlock = CodeBlock().preset(CodeBlockProps(language="typescript"))

PythonBlock = CodeBlock().preset(CodeBlockProps(language="python"))
