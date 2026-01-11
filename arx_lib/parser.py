from sly import Parser
from sly.lex import Token
from .lexer import ArtemisLexer
from .helpers import ArtemisParserLogger
from typing import Any, Optional

class ArtemisParser(Parser):
    tokens : set[str] = ArtemisLexer.tokens
    log : ArtemisParserLogger = ArtemisParserLogger()

    precedence : tuple = (
        ('left', 'OR'),
        ('left', 'AND'),
        ('right', 'NOT'),
        ('nonassoc', 'EQEQ', 'NOTEQ', 'LTEQ', 'GTEQ', 'LT', 'GT'),
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE', 'PERCENT'),
    )

    def __init__(self) -> None:
        self.using_modules = []

    # ----- PROGRAM -----

    @_('using_directive_list top_level_list')  # type: ignore[name-defined]
    def program(self, p) -> tuple:
        return ('program', p.using_directive_list, p.top_level_list)


    @_('top_level_list')  # type: ignore[name-defined]
    def program(self, p) -> tuple:
        return ('program', [], p.top_level_list)

    # ----- USING DIRECTIVES -----

    @_('USING ID') # type: ignore[name-defined]
    def using_directive(self, p) -> tuple:
        self.using_modules.append(p.ID)
        return ('using', p.ID)

    @_('using_directive using_directive_list') # type: ignore[name-defined]
    def using_directive_list(self, p) -> list:
        return [p.using_directive] + p.using_directive_list

    @_('using_directive') # type: ignore[name-defined]
    def using_directive_list(self, p) -> list:
        return [p.using_directive]

    # ----- TOP LEVEL DECLARATIONS -----

    @_('top_level top_level_list')  # type: ignore[name-defined]
    def top_level_list(self, p) -> list:
        return [p.top_level] + p.top_level_list

    @_('top_level')  # type: ignore[name-defined]
    def top_level_list(self, p) -> list:
        return [p.top_level]

    @_('function')  # type: ignore[name-defined]
    def top_level(self, p) -> tuple:
        return p.function

    @_('class_declaration')  # type: ignore[name-defined]
    def top_level(self, p) -> tuple:
        return p.class_declaration

    # ----- FUNCTION CALL -----

    @_('type ID LPAREN RPAREN LBRACE statements RBRACE') # type: ignore[name-defined]
    def function(self, p) -> tuple:
        return ('function', p.ID, [], p.statements, p.type)

    @_('type ID LPAREN param_list RPAREN LBRACE statements RBRACE') # type: ignore[name-defined]
    def function(self, p) -> tuple:
        return ('function', p.ID, p.param_list, p.statements, p.type)

    # ----- PARAMETERS -----

    @_('param COMMA param_list') # type: ignore[name-defined]
    def param_list(self, p) -> list:
        return [p.param] + p.param_list

    @_('param') # type: ignore[name-defined]
    def param_list(self, p) -> list:
        return [p.param]

    @_('INT ID') # type: ignore[name-defined]
    def param(self, p) -> tuple:
        return ('param', 'int', p.ID)

    @_('FLOAT ID') # type: ignore[name-defined]
    def param(self, p) -> tuple:
        return ('param', 'float', p.ID)

    @_('STR ID') # type: ignore[name-defined]
    def param(self, p) -> tuple:
        return ('param', 'str', p.ID)

    @_('BOOL ID') # type: ignore[name-defined]
    def param(self, p) -> tuple:
        return ('param', 'bool', p.ID)

    # ----- STATEMENTS -----

    @_('statements statement') # type: ignore[name-defined]
    def statements(self, p) -> list:
        return p.statements + [p.statement]

    @_('') # type: ignore[name-defined]
    def statements(self, p) -> list:
        return []

    @_('expression') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('expression', p.expression)

    @_('RETURN expression') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('return', p.expression)

    @_('RETURN') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('return_void',)

    # -- IF / ELSE IF / ELSE CHAIN --

    @_('IF LPAREN expression RPAREN LBRACE statements RBRACE elseif_chain') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('if_chain', [(p.expression, p.statements)] + p.elseif_chain)

    @_('ELSE IF LPAREN expression RPAREN LBRACE statements RBRACE elseif_chain') # type: ignore[name-defined]
    def elseif_chain(self, p) -> list:
        return [(p.expression, p.statements)] + p.elseif_chain

    @_('ELSE LBRACE statements RBRACE') # type: ignore[name-defined]
    def elseif_chain(self, p) -> list:
        return [(None, p.statements)]

    @_('') # type: ignore[name-defined]
    def elseif_chain(self, p) -> list:
        return []

    # ----- FOR -----

    @_('FOR LPAREN type ID IN ID RPAREN LBRACE statements RBRACE') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('for_in', p.type, p.ID0, p.ID1, p.statements)

    # ----- WHILE -----

    @_('WHILE LPAREN expression RPAREN LBRACE statements RBRACE')  # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('while', p.expression, p.statements)

    # ----- ADD / SUBSTRACT -----

    @_('expression PLUSPLUS')    # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('postinc', p.expression)

    @_('expression MINUSMINUS')  # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('postdec', p.expression)

    # ----- OPS -----

    @_('expression PLUS expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '+', p.expression0, p.expression1)

    @_('expression MINUS expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '-', p.expression0, p.expression1)

    @_('expression TIMES expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '*', p.expression0, p.expression1)

    @_('expression DIVIDE expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '/', p.expression0, p.expression1)

    @_('expression PERCENT expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '%', p.expression0, p.expression1)

    @_('expression EQEQ expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '==', p.expression0, p.expression1)

    @_('expression NOTEQ expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '!=', p.expression0, p.expression1)

    @_('expression LTEQ expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '<=', p.expression0, p.expression1)

    @_('expression GTEQ expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '>=', p.expression0, p.expression1)

    @_('expression GT expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '>', p.expression0, p.expression1)

    @_('expression LT expression') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', '<', p.expression0, p.expression1)

    # ----- LOGICAL OPS -----

    @_('expression OR expression')   # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', 'or', p.expression0, p.expression1)

    @_('expression AND expression')   # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('binop', 'and', p.expression0, p.expression1)

    @_('NOT expression')   # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('unop', 'not', p.expression)

    # ----- TYPES -----

    @_('INT') # type: ignore[name-defined]
    def type(self, p) -> str:
        return 'int'

    @_('BOOL') # type: ignore[name-defined]
    def type(self, p) -> str:
        return 'bool'

    @_('FLOAT') # type: ignore[name-defined]
    def type(self, p) -> str:
        return 'float'

    @_('STR') # type: ignore[name-defined]
    def type(self, p) -> str:
        return 'string'

    @_('VOID') # type: ignore[name-defined]
    def type(self, p) -> str:
        return 'void'

    # ----- EXPRESSIONS -----

    @_('type ID ASSIGN expression') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('declare', p.type, p.ID, p.expression)

    @_('ID ASSIGN expression')  # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('assign', p.ID, p.expression)

    @_('LIST COLON type ID ASSIGN expression') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('declare_list', p.type, p.ID, p.expression)

    @_('ANY COLON ID ID ASSIGN expression') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('declare_custom', p.ID0, p.ID1, p.expression)

    @_('expression ASSIGN expression') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('assign', p.expression0, p.expression1)

    @_('BREAK') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('break',)

    @_('CONTINUE') # type: ignore[name-defined]
    def statement(self, p) -> tuple:
        return ('continue',)

    @_('STRING') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('string', p.STRING)

    @_('FLOATNUMBER') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('float', p.FLOATNUMBER)

    @_('NUMBER') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('int', p.NUMBER)

    @_('TRUE') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('bool', True)

    @_('FALSE') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('bool', False)

    @_('object_creation') # type: ignore[name-defined]
    def expression(self, p) -> Any:
        return p.object_creation

    # ----- THIS -----

    @_('THIS') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('this',)

    # ----- LISTS -----

    @_('LBRACKET list_elements RBRACKET') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('list_literal', p.list_elements)

    @_('expression COMMA list_elements') # type: ignore[name-defined]
    def list_elements(self, p) -> list:
        return [p.expression] + p.list_elements

    @_('expression') # type: ignore[name-defined]
    def list_elements(self, p) -> list:
        return [p.expression]

    # ----- FUNCTION ARGUMENTS -----

    @_('') # type: ignore[name-defined]
    def args(self, p) -> list:
        return []

    @_('expression') # type: ignore[name-defined]
    def args(self, p) -> list:
        return [p.expression]

    @_('args COMMA expression') # type: ignore[name-defined]
    def args(self, p) -> list:
        return p.args + [p.expression]

    @_('ID') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('var', p.ID)

    @_('LPAREN expression RPAREN') # type: ignore[name-defined]
    def expression(self, p) -> list:
        return p.expression

    # ----- FUNCTION CALL -----

    @_('ID LPAREN args RPAREN') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('call', p.ID, p.args)

    @_('ID LPAREN RPAREN') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('call', p.ID, [])

    # ----- CLASSES -----

    @_('CLASS ID LBRACE class_body RBRACE') # type: ignore[name-defined]
    def class_declaration(self, p) -> tuple:
        return ('class', p.ID, p.class_body)

    @_('class_member class_body') # type: ignore[name-defined]
    def class_body(self, p) -> list:
        return [p.class_member] + p.class_body

    @_('class_member') # type: ignore[name-defined]
    def class_body(self, p) -> list:
        return [p.class_member]

    @_('method') # type: ignore[name-defined]
    def class_member(self, p) -> Any:
        return p.method

    @_('field') # type: ignore[name-defined]
    def class_member(self, p) -> Any:
        return p.field

    @_('type ID LPAREN param_list RPAREN LBRACE statements RBRACE') # type: ignore[name-defined]
    def method(self, p) -> tuple:
        return ('method', p.type, p.ID, p.param_list, p.statements)

    @_('type ID LPAREN RPAREN LBRACE statements RBRACE') # type: ignore[name-defined]
    def method(self, p) -> tuple:
        return ('method', p.type, p.ID, [], p.statements)

    @_('ID LPAREN args RPAREN') # type: ignore[name-defined]
    def object_creation(self, p) -> tuple:
        return ('object_creation', p.ID, p.args)

    @_('type ID ASSIGN expression') # type: ignore[name-defined]
    def field(self, p) -> tuple[str, str, str, Any]:
        return ('field', p.type, p.ID, p.expression)

    @_('type ID') # type: ignore[name-defined]
    def field(self, p) -> tuple[str, str, str, Optional[Any]]:
        return ('field', p.type, p.ID, None)

    # ----- MEMBER ACCESS -----

    @_('expression DOT ID') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('get_attr', p.expression, p.ID)

    @_('expression DOT ID LPAREN args RPAREN') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('call_method', p.expression, p.ID, p.args)

    @_('expression DOT ID LPAREN RPAREN') # type: ignore[name-defined]
    def expression(self, p) -> tuple:
        return ('call_method', p.expression, p.ID, [])
