from sly import Lexer
from sly.lex import Token

class ArtemisLexer(Lexer):
    tokens : set[str] = {
        'USING',
        'INT', 'FLOAT', 'LIST', 'STR', 'ANY', 'VOID', 'CLASS', 'THIS', 'BOOL',
        'TRUE', 'FALSE', 'NOT', 'OR', 'AND',
        'ID', 'NUMBER', 'FLOATNUMBER', 'STRING',
        'EQEQ', 'NOTEQ', 'LTEQ', 'GTEQ', 'LT', 'GT',
        'PLUSPLUS', 'MINUSMINUS', 'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'PERCENT',
        'ASSIGN', 'COLON', 'COMMA', 'IF', 'ELSE', 'WHILE', 'FOR', 'IN', 'BREAK', 'CONTINUE',
        'LBRACE', 'RBRACE', 'LPAREN', 'RPAREN', 'LBRACKET', 'RBRACKET', 'DOT', 'RETURN',
    }

    ignore : str = ' \t'

    ignore_comment : str = r'//.*'


    ignore_newline : str = r'\n+'
    def ignore_newline(self, token:Token) -> None:
        self.lineno += token.value.count('\n')

    EQEQ  : str = r'=='
    NOTEQ : str = r'!='
    LTEQ  : str = r'<='
    GTEQ  : str = r'>='
    LT    : str   = r'<'
    GT    : str   = r'>'
    PLUSPLUS   : str = r'\+\+'
    MINUSMINUS : str = r'--'
    PLUS  : str = r'\+'
    MINUS : str = r'-'
    TIMES : str = r'\*'
    DIVIDE : str = r'/'
    ASSIGN : str = r'='
    COLON : str = r':'
    COMMA : str = r','
    DOT   : str = r'\.'
    PERCENT : str = r'\%'

    LBRACE   : str = r'\{'
    RBRACE   : str = r'\}'
    LPAREN   : str = r'\('
    RPAREN   : str = r'\)'
    LBRACKET : str = r'\['
    RBRACKET : str = r'\]'

    INT : str = r'int(:\d+)?'
    def INT(self, token:Token) -> Token:
        if ':' in token.value:
            token.value = int(token.value.split(':')[1])
        else:
            token.value = None
        return token

    FLOAT : str = r'float(:\d+)?'
    def FLOAT(self, token:Token) -> Token:
        if ':' in token.value:
            token.value = int(token.value.split(':')[1])
        else:
            token.value = None
        return token

    ID : str = r'[a-zA-Z_][a-zA-Z0-9_]*'
    def ID(self, token:Token) -> Token:
        keywords = {
            'using' : 'USING',
            'string' : 'STR',
            'list' : 'LIST',
            'any' : 'ANY',
            'void' : 'VOID',
            'class' : 'CLASS',
            'this' : 'THIS',
            'true' : 'TRUE',
            'false' : 'FALSE',
            'return' : 'RETURN',
            'bool' : 'BOOL',
            'if' : 'IF',
            'else' : 'ELSE',
            'while' : 'WHILE',
            'for' : 'FOR',
            'in' : 'IN',
            'break' : 'BREAK',
            'continue' : 'CONTINUE',
            'not' : 'NOT',
            'and' : 'AND',
            'or' : 'OR'
        }
        token.type = keywords.get(token.value, 'ID')
        return token

    FLOATNUMBER : str = r'\d+\.\d+'
    def FLOATNUMBER(self, token:Token) -> Token:
        token.value = float(token.value)
        return token

    NUMBER : str = r'\d+'
    def NUMBER(self, token:Token) -> Token:
        token.value = int(token.value)
        return token

    STRING : str = r"'([^\\']|\\.)*'"
    def STRING(self, token:Token) -> Token:
        raw = token.value[1:-1]
        token.value = bytes(raw, 'utf-8').decode('unicode_escape')
        return token

    def error(self, token:Token) -> None:
        print(f'Illegal character {token.value[0]!r} at line {self.lineno}')
        self.index += 1
