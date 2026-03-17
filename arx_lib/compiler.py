from llvmlite import ir, binding
import os, sys
import glob, shutil
import configparser
import re
import copy
from .helpers import debug_print, arx_extension
from .data_classes import ArtemisData, TypeEnum
from .converters import ir_to_string, string_to_ir
from .lexer import ArtemisLexer
from .parser import ArtemisParser
from typing import Union, Optional, ItemsView, Any, Iterator, Iterable

def parse_file(file_in: str) -> tuple:
    with open(file_in) as f:
        file_contents = f.read()
    lexer : ArtemisLexer = ArtemisLexer()
    parser : ArtemisParser = ArtemisParser()
    tokens : list = list(lexer.tokenize(file_contents))
    debug_print(tokens)
    ast : tuple = parser.parse(iter(tokens))
    if not ast:
        raise RuntimeError('Parsing failed')
    debug_print(ast)
    return ast

def parse_function_overloads(items:ItemsView[str, str], module_name: str) -> dict:
    externs: dict = {}
    for signature, mapping in items:
        signature : str = signature.strip()
        mapping : str = mapping.strip()
        if not signature or not mapping:
            continue
        function_name, argument_part = (signature.split(':', 1) + [''])[:2]
        function_name : str = function_name.strip()
        argument_types : tuple = tuple(arg.strip() for arg in argument_part.split(',') if arg.strip())
        llvm_name, return_type = map(str.strip, mapping.split('>'))
        key : str = f'{module_name}.{function_name}'
        externs.setdefault(key, {})[argument_types] = (llvm_name, return_type)
    return externs


class ArtemisCompiler:
    def __init__(self, compiler_data: ArtemisData) -> None:
        binding.initialize()
        binding.initialize_native_target()
        binding.initialize_native_asmprinter()
        self.module: ir.Module = ir.Module(name='arx')
        self.module.triple = binding.get_default_triple()
        self.target : binding.Target = binding.Target.from_default_triple()
        self.target_machine : binding.TargetMachine = self.target.create_target_machine()
        self.builder : Optional[ir.IRBuilder] = None
        self.func : Optional[ir.Function] = None
        self.compiler_data: ArtemisData = compiler_data
        self.variables : dict[str, tuple[ir.AllocaInstr, ir.Type]] = {}
        self.local_vars: dict[str, ir.AllocaInstr] = {}
        self.loop_continue_stack: list[ir.Block] = []
        self.loop_break_stack: list[ir.Block] = []
        self.loop_counter : int = 0
        self.function_counter : int = 0
        self.if_counter : int = 0
        self.get_abi_counter : int = 0
        self.extern_c: set[str] = set()
        self.extern_functions: dict[str, dict] = {}
        self.extern_modules: dict[str, ir.Module] = {}
        self.extern_modules_namespace: dict[str, dict[str, str]] = {}
        self.list_struct_type : ir.IdentifiedStructType = ir.global_context.get_identified_type('List')
        if compiler_data.is_main:
            self.list_struct_type.set_body(
                TypeEnum.int8.as_pointer(),
                TypeEnum.int32,
                TypeEnum.int32,
                TypeEnum.int64,
                TypeEnum.boolean
            )

    def get_abi_size_from_ir_type(self, ir_type: ir.Type) -> int:
        if isinstance(ir_type, ir.IntType):
            return ir_type.width // 8
        elif isinstance(ir_type, ir.PointerType):
            return 8
        elif isinstance(ir_type, ir.FloatType):
            return 4
        elif isinstance(ir_type, ir.DoubleType):
            return 8
        elif isinstance(ir_type, ir.ArrayType):
            element_size : int = self.get_abi_size_from_ir_type(ir_type.element)
            return element_size * ir_type.count
        elif isinstance(ir_type, ir.LiteralStructType) or isinstance(ir_type, ir.IdentifiedStructType):
            total_size : int = 0
            for elem in ir_type.elements:
                total_size += self.get_abi_size_from_ir_type(elem)
            return total_size
        else:
            raise NotImplementedError(f'ABI size calculation not implemented for {ir_type}')

    def safe_store(self, value: ir.Value, pointer: ir.AllocaInstr):
        target_type = pointer.type.pointee
        if target_type != value.type:
            if target_type.is_pointer and value.type.is_pointer:
                value = self.builder.bitcast(value, target_type)
            else:
                raise TypeError(f'Cannot assign {value.type} to {target_type}')
        self.builder.store(value, pointer)

    def allocate_and_copy_array(self, elements: list[ir.Value], element_type: ir.Type) -> ir.Value:
        element_count : int = len(elements)
        element_size : int = self.get_abi_size_from_ir_type(element_type)
        total_size : ir.Constant = ir.Constant(TypeEnum.int32, element_count * element_size)
        malloc_function : ir.Function = self.declare_malloc()
        heap_pointer = self.builder.call(malloc_function, [self.builder.zext(total_size, TypeEnum.int64)], name='heap_pointer')
        typed_pointer = self.builder.bitcast(heap_pointer, element_type.as_pointer())
        for i, element in enumerate(elements):
            index = ir.Constant(TypeEnum.int32, i)
            element_address = self.builder.gep(typed_pointer, [index], name=f'element_pointer_{i}')
            element_value : ir.Value = element
            if element.type.is_pointer and not element.type == element_type:
                element_value = self.builder.load(element)
            self.safe_store(element_value, element_address)
        return heap_pointer

    def load_externs_c(self, using_externs: list[str]) -> None:
        for path in self.compiler_data.map_paths:
            map_files = glob.glob(os.path.join(path, '*.map'))
            for map_file in map_files:
                cfg : configparser.RawConfigParser = configparser.RawConfigParser(delimiters=('='))
                cfg.read(map_file)
                module_name : str = cfg['meta']['name']
                if (module_name != 'core') and (module_name not in using_externs):
                    continue
                self.extern_c.add(module_name)
                externs : dict = parse_function_overloads(cfg['functions'].items(), module_name)
                for full_name, overloads in externs.items():
                    self.extern_functions.setdefault(full_name, {}).update(overloads)

    def load_using(self, using_list: set[str], search_dir: str) -> None:
        arx_using : set[str] = { arx_file for arx_file in using_list if os.path.exists(os.path.join(search_dir, arx_file + arx_extension)) }
        c_using : set[str] = using_list.difference(arx_using)
        for arx_module in arx_using:
            sub_c, sub_module = self.compile_sub(arx_module, search_dir)
            self.extern_c.update(sub_c)
        self.load_externs_c(c_using)

    def declare_malloc(self) -> ir.Function:
        malloc_type : ir.FunctionType = ir.FunctionType(TypeEnum.int8.as_pointer(), [TypeEnum.int64])
        malloc_function : ir.Function = self.module.globals.get('malloc')
        if malloc_function is None:
            malloc_function = ir.Function(self.module, malloc_type, name='malloc')
        return malloc_function

    def declare_list_len(self) -> ir.Function:
        if not hasattr(self, 'list_len_func'):
            function_type : ir.FunctionType = ir.FunctionType(TypeEnum.int32, [self.list_struct_type.as_pointer()])
            self.list_len_function : ir.Function = ir.Function(self.module, function_type, name='core_list_len')
        return self.list_len_function

    def call_list_len(self, list_pointer:ir.AllocaInstr) -> ir.CallInstr:
        return self.builder.call(self.declare_list_len(), [list_pointer])

    def declare_list_get(self) -> ir.Function:
        if not hasattr(self, 'list_get_func'):
            function_type : ir.FunctionType = ir.FunctionType(TypeEnum.int8.as_pointer(), [self.list_struct_type.as_pointer(), TypeEnum.int32])
            self.list_get_func : ir.Function = ir.Function(self.module, function_type, name='core_list_get')
        return self.list_get_func

    def call_list_get(self, list_pointer:ir.AllocaInstr, index_value:ir.LoadInstr) -> ir.CallInstr:
        return self.builder.call(self.declare_list_get(), [list_pointer, index_value])

    def compile_function(self, node:tuple):
        _tag, name, parameters, statements, return_type = node
        argument_types : list[ir.Type] = [string_to_ir(parameter_type) for _id, parameter_type, _name in parameters]
        function_type : ir.FunctionType = ir.FunctionType(string_to_ir(return_type), argument_types)
        self.func : ir.Function = ir.Function(self.module, function_type, name=name)
        block : ir.Block = self.func.append_basic_block(f'entry_{self.function_counter}')
        self.function_counter += 1
        self.builder : ir.IRBuilder = ir.IRBuilder(block)
        self.variables = {}
        self.current_function_return_type : str = return_type
        for i, (_id, _type, name) in enumerate(parameters):
            argument = self.func.args[i]
            argument.name = name
            pointer : ir.AllocaInstr = self.builder.alloca(argument.type, name=name)
            self.safe_store(argument, pointer)
            self.variables[name] = (pointer, argument.type)
        for statement in statements:
            self.compile_statement(statement)
        if self.builder.block.terminator is None:
            raise Exception(f'Missing return in function {name}')

    def compile_class(self, node:tuple) -> None:
        _tag, name, body = node
        fields = [member for member in body if member[0] == 'field']
        methods = [member for member in body if member[0] == 'method']
        struct_type = ir.global_context.get_identified_type(name)
        field_types = [string_to_ir(field_type) for _tag, field_type, _id, _value in fields]
        struct_type.set_body(*field_types)
        self.compiler_data.class_bodies[name] = {
            'fields': fields,
            'methods': methods,
            'struct': struct_type
        }
        self.current_class = name
        for method in methods:
            self.compile_method(name, method)
        self.current_class = None

    def compile_sub(self, sub_module:str, search_dir:str) -> tuple[set[str], ir.Module]:
        if sub_module in self.extern_modules:
            return (self.extern_c, self.extern_modules[sub_module])
        sub_compiler_data : ArtemisData = copy.deepcopy(self.compiler_data)
        sub_compiler_data.is_main = False
        sub_compiler : ArtemisCompiler = ArtemisCompiler(sub_compiler_data)
        ast : tuple = parse_file(os.path.join(search_dir, sub_module + arx_extension))
        using_modules : set[str] = {mod[1] for mod in ast[1]}
        debug_print(using_modules)
        body : tuple = ast[2]
        sub_compiler.load_using(using_modules, search_dir)
        for section in body:
            match section[0]:
                case 'function':
                    sub_compiler.compile_function(section)
                case 'class':
                    sub_compiler.compile_class(section)
        namespace_map : dict[str, str] = {}
        self.extern_c.update(sub_compiler.extern_c)
        for unmangled_name, global_value in list(sub_compiler.module.globals.items()):
            mangled_name : str = f'{sub_module}_{unmangled_name}'
            is_c : bool = False
            for c_lib in [f'{c}_' for c in self.extern_c]:
                if unmangled_name.startswith(c_lib):
                    is_c = True
            if is_c:
                continue
            global_value.name = mangled_name
            sub_compiler.module.globals[mangled_name] = sub_compiler.module.globals.pop(unmangled_name)
            namespace_map[unmangled_name] = mangled_name
        self.extern_modules_namespace[sub_module] = namespace_map
        self.extern_modules[sub_module] = sub_compiler.module
        return (sub_compiler.extern_c, sub_compiler.module)

    def compile_exec(self, file_in:str) -> str:
        ast : tuple = parse_file(file_in)
        using_modules : set = {mod[1] for mod in ast[1]}
        debug_print(using_modules)
        body : tuple = ast[2]
        self.load_using(using_modules, os.path.dirname(file_in))
        for section in body:
            match section[0]:
                case 'function':
                    self.compile_function(section)
                case 'class':
                    self.compile_class(section)
        self.add_c_main()
        exec_module_lines : list[str] = str(self.module).splitlines()
        final_ir_lines : list[str] = []
        declare_set : set[str] = set()
        definition_set : set[str] = set()
        for line in exec_module_lines:
            if not line.startswith('; ModuleID'):
                final_ir_lines.append(line)
            if line.startswith('declare'):
                declare_set.add(line)
            if line.startswith('%"List"'):
                definition_set.add(line)
        for sub_name, sub_module in self.extern_modules.items():
            sub_ir_lines = str(sub_module).splitlines()
            for line in sub_ir_lines:
                if line.startswith('; ModuleID') or line.startswith('target triple') or line.startswith('target datalayout'):
                    continue
                if line.startswith('declare'):
                    if line in declare_set:
                        continue
                    declare_set.add(line)
                if line.startswith('%"List"'):
                    if line in definition_set:
                        continue
                    definition_set.add(line)
                for unmangled_name, mangled_name in self.extern_modules_namespace[sub_name].items():
                    line = line.replace(f'@{unmangled_name}', f'@{mangled_name}')
                final_ir_lines.append(line)
        exec_module : str = '\n'.join(final_ir_lines)
        exec_binding : binding.ModuleRef = binding.parse_assembly(exec_module)
        exec_binding.verify()
        return str(exec_binding)

    def compile_this_access(self, field_name:str) -> ir.LoadInstr:
        field_pointer : ir.GEPInstr = self.get_this_field_pointer(field_name)
        return self.builder.load(field_pointer)

    def get_this_field_pointer(self, field_name:str) -> ir.GEPInstr:
        this_pointer = self.local_vars.get('this')
        if not this_pointer:
            raise RuntimeError('this used outside of method')
        class_name = getattr(self, 'current_class', None)
        if not class_name:
            raise RuntimeError('No current_class while compiling this access')
        fields = self.compiler_data.class_bodies[class_name]['fields']
        index = next((i for i, (_, _, field_name_match, _) in enumerate(fields) if field_name_match == field_name), None)
        if index is None:
            raise NameError(f'Field {field_name} not found on {class_name}')
        return self.builder.gep(this_pointer, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)])

    def get_field_pointer_general(self, object_expression:tuple, field_name:str) -> ir.GEPInstr:
        if object_expression == ('this',) or (isinstance(object_expression, tuple) and len(object_expression) == 1 and object_expression[0] == 'this'):
            return self.get_this_field_pointer(field_name)
        if isinstance(object_expression, tuple):
            if len(object_expression) == 2 and object_expression[0] == 'var':
                variable_name = object_expression[1]
            else:
                variable_name = object_expression[0]
        elif isinstance(object_expression, str):
            variable_name = object_expression
        else:
            raise RuntimeError(f'Unexpected object expression for field access: {object_expression}')
        if variable_name not in self.variables:
            raise NameError(f'Undefined variable (object) for field access: {variable_name}')
        object_pointer, object_type = self.variables[variable_name]
        class_name = getattr(getattr(object_type, 'pointee', None), 'name', None)
        if not class_name:
            raise RuntimeError(f'Object {variable_name} does not have a valid class type')
        fields = self.compiler_data.class_bodies[class_name]['fields']
        index = next((i for i, (_, _, function_name, _) in enumerate(fields) if function_name == field_name), None)
        if index is None:
            raise NameError(f'Field {field_name} not found on {class_name}')
        return self.builder.gep(object_pointer, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)])

    def compile_method(self, class_name: str, method_node: tuple) -> None:
        _tag, return_type, method_name, parameters, statements = method_node
        mangled = f'{class_name}_{method_name}'
        struct_type: ir.IdentifiedStructType = self.compiler_data.class_bodies[class_name]['struct']
        this_ir: ir.PointerType = struct_type.as_pointer()
        parameter_types = [string_to_ir(type_) for _, type_, _ in parameters]
        parameter_names = [name for _, _, name in parameters]
        return_ir = string_to_ir(return_type) if return_type != 'void' else ir.VoidType()
        function_type = ir.FunctionType(return_ir, [this_ir] + parameter_types)
        function = self.module.globals.get(mangled)
        if not function:
            function = ir.Function(self.module, function_type, name=mangled)
        block = function.append_basic_block('entry')
        builder = ir.IRBuilder(block)
        previous_builder = self.builder
        previous_function = self.func
        self.builder = builder
        self.func = function
        self.local_vars = {}
        arguments_iter = iter(function.args)
        this_argument = next(arguments_iter)
        self.local_vars['this'] = this_argument
        for name, llvm_arg in zip(parameter_names, arguments_iter):
            a_pointer = builder.alloca(llvm_arg.type)
            builder.store(llvm_arg, a_pointer)
            self.local_vars[name] = a_pointer
        if method_name == '_init':
            fields = self.compiler_data.class_bodies[class_name]['fields']
            for i, (_tag, _function_type, _function_name, init_expression) in enumerate(fields):
                field_pointer = self.builder.gep(
                    this_argument,
                    [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), i)]
                )
                if i < len(parameter_names):
                    parameter_value = self.builder.load(self.local_vars[parameter_names[i]])
                    if field_pointer.type.pointee != param_val.type:
                        parameter_value = self.builder.bitcast(parameter_value, field_pointer.type.pointee)
                    builder.store(parameter_value, field_pointer)
                elif init_expression is not None:
                    value = self.compile_expression(init_expression)
                    if field_pointer.type.pointee != value.type:
                        value = self.builder.bitcast(value, field_pointer.type.pointee)
                    builder.store(value, field_pointer)
        for statement in statements:
            self.compile_statement(statement)
        if return_ir != ir.VoidType() and not builder.block.is_terminated:
            builder.ret(ir.Constant(return_ir, 0))
        elif return_ir == ir.VoidType() and not builder.block.is_terminated:
            builder.ret_void()
        self.builder = previous_builder
        self.func = previous_function

    def compile_statement(self, statement:tuple) -> None:
        kind : str = statement[0]
        match kind:
            case 'expression':
                self.compile_expression(statement[1])
            case 'return':
                return_value = self.compile_expression(statement[1])
                self.builder.ret(return_value)
            case 'return_void':
                if self.current_function_return_type != 'void':
                    raise TypeError('Void return used in non-void function')
                self.builder.ret_void()
            case 'declare':
                variable_type_string, variable_name, value_expression = statement[1], statement[2], statement[3]
                value = self.compile_expression(value_expression)
                match variable_type_string:
                    case 'int':
                        pointer : ir.AllocaInstr = self.builder.alloca(TypeEnum.int32, name=variable_name)
                        self.safe_store(value, pointer)
                        self.variables[variable_name] = (pointer, value.type)
                    case 'float':
                        pointer : ir.AllocaInstr = self.builder.alloca(TypeEnum.float32, name=variable_name)
                        self.safe_store(value, pointer)
                        self.variables[variable_name] = (pointer, value.type)
                    case 'bool':
                        pointer : ir.AllocaInstr = self.builder.alloca(TypeEnum.boolean, name=variable_name)
                        self.safe_store(value, pointer)
                        self.variables[variable_name] = (pointer, value.type)
                    case 'string':
                        pointer : ir.AllocaInstr = self.builder.alloca(TypeEnum.string, name=variable_name)
                        self.safe_store(value, pointer)
                        self.variables[variable_name] = (pointer, value.type)
                    case _:
                        raise NotImplementedError(f'Unsupported type: {variable_type_string}')
            case 'declare_custom':
                type_name, variable_name, constructor_call = statement[1], statement[2], statement[3]
                if constructor_call[0] == 'call' and constructor_call[1] == type_name:
                    object_pointer = self.compile_expression(('object_creation', type_name, constructor_call[2]))
                else:
                    object_pointer = self.compile_expression(constructor_call)
                self.variables[variable_name] = (object_pointer, object_pointer.type)
            case 'if_chain':
                branches = statement[1]
                end_block : ir.Block = self.func.append_basic_block(f'if_end_{self.if_counter}')
                self.if_counter += 1
                has_fallthrough : bool = False
                for i, (condition_expression, statements) in enumerate(branches):
                    then_block : ir.Block = self.func.append_basic_block(f'if_then_{i}')
                    next_block : ir.Block = self.func.append_basic_block(f'if_next_{i}') if i < len(branches) - 1 else end_block
                    if condition_expression is not None:
                        condition_value : ir.Value = self.compile_expression(condition_expression)
                        self.builder.cbranch(condition_value, then_block, next_block)
                    else:
                        self.builder.branch(then_block)
                    self.builder.position_at_start(then_block)
                    for statement in statements:
                        self.compile_statement(statement)
                    if self.builder.block.terminator is None:
                        self.builder.branch(end_block)
                        has_fallthrough = True
                    if condition_expression is not None:
                        self.builder.position_at_start(next_block)
                if has_fallthrough and not end_block.is_terminated:
                    self.builder.position_at_start(end_block)
            case 'for_in':
                variable_type, variable_name, list_name, body = statement[1], statement[2], statement[3], statement[4]
                index_pointer : ir.AllocaInstr = self.builder.alloca(TypeEnum.int32, name=f"{variable_name}_index")
                self.safe_store(ir.Constant(TypeEnum.int32, 0), index_pointer)
                conditional_block : ir.Block = self.func.append_basic_block(f'for_conditional_{self.loop_counter}')
                body_block : ir.Block = self.func.append_basic_block(f'for_body_{self.loop_counter}')
                end_block : ir.Block = self.func.append_basic_block(f'for_end_{self.loop_counter}')
                continue_block : ir.Block = self.func.append_basic_block(f'for_continue_{self.loop_counter}')
                self.loop_counter += 1
                self.builder.branch(conditional_block)
                self.builder.position_at_start(conditional_block)
                list_pointer : ir.AllocaInstr = self.variables[list_name][0]
                index_value : ir.LoadInstr = self.builder.load(index_pointer)
                list_len : ir.CallInstr = self.call_list_len(list_pointer)
                conditional : ir.ICMPInstr = self.builder.icmp_signed('<', index_value, list_len)
                self.builder.cbranch(conditional, body_block, end_block)
                self.builder.position_at_start(body_block)
                element_pointer : ir.CallInstr = self.call_list_get(list_pointer, index_value)
                element_type : ir.Type = string_to_ir(variable_type)
                element_value : Any = None
                if element_type.is_pointer:
                    element_value = self.builder.bitcast(element_pointer, element_type)
                else:
                    casted_pointer = self.builder.bitcast(
                        element_pointer,
                        element_type.as_pointer()
                    )
                    element_value = self.builder.load(casted_pointer)
                variable_pointer = self.builder.alloca(string_to_ir(variable_type), name=variable_name)
                self.safe_store(element_value, variable_pointer)
                self.variables[variable_name] = (variable_pointer, string_to_ir(variable_type))
                self.loop_continue_stack.append(continue_block)
                self.loop_break_stack.append(end_block)
                for for_in_statement in body:
                    self.compile_statement(for_in_statement)
                self.loop_continue_stack.pop()
                self.loop_break_stack.pop()
                self.builder.branch(continue_block)
                self.builder.position_at_start(continue_block)
                new_index : ir.Value = self.builder.add(index_value, ir.Constant(TypeEnum.int32, 1))
                self.safe_store(new_index, index_pointer)
                self.builder.branch(conditional_block)
                self.builder.position_at_start(end_block)
            case 'while':
                condition_expression, body = statement[1], statement[2]
                condition_block: ir.Block = self.func.append_basic_block(f'while_conditional_{self.loop_counter}')
                body_block: ir.Block = self.func.append_basic_block(f'while_body_{self.loop_counter}')
                end_block: ir.Block = self.func.append_basic_block(f'while_end_{self.loop_counter}')
                continue_block: ir.Block = self.func.append_basic_block(f'while_continue_{self.loop_counter}')
                self.loop_counter += 1
                self.builder.branch(condition_block)
                self.builder.position_at_start(condition_block)
                condition_value: ir.Value = self.compile_expression(condition_expression)
                self.builder.cbranch(condition_value, body_block, end_block)
                self.builder.position_at_start(body_block)
                self.loop_break_stack.append(end_block)
                self.loop_continue_stack.append(continue_block)
                for in_while_statement in body:
                    self.compile_statement(in_while_statement)
                self.loop_break_stack.pop()
                self.loop_continue_stack.pop()
                self.builder.branch(continue_block)
                self.builder.position_at_start(continue_block)
                self.builder.branch(condition_block)
                self.builder.position_at_start(end_block)
            case 'declare_list':
                element_type, name, expression = statement[1], statement[2], statement[3]
                if expression[0] == 'list_literal':
                    elements = [self.compile_expression(e) for e in expression[1]]
                    llvm_element_type : ir.Type = string_to_ir(element_type)
                    heap_pointer : ir.Value = self.allocate_and_copy_array(elements, llvm_element_type)
                    create_function_type : ir.FunctionType = ir.FunctionType(
                        self.list_struct_type.as_pointer(),
                        [TypeEnum.int8.as_pointer(), TypeEnum.int32, TypeEnum.int32, TypeEnum.boolean]
                    )
                    create_function : ir.Function = self.module.globals.get('core_list_create_from')
                    if create_function is None:
                        create_function = ir.Function(self.module, create_function_type, name='core_list_create_from')
                    element_size_bytes : int = self.get_abi_size_from_ir_type(llvm_element_type)
                    list_pointer = self.builder.call(
                        create_function,
                        [
                            heap_pointer,
                            ir.Constant(TypeEnum.int32, len(elements)),
                            ir.Constant(TypeEnum.int32, element_size_bytes),
                            ir.Constant(TypeEnum.boolean, int(llvm_element_type.is_pointer))
                        ]
                    )
                    self.variables[name] = (list_pointer, self.list_struct_type.as_pointer())
                else:
                    value : ir.CallInstr = self.compile_expression(expression)
                    self.variables[name] = (value, value.type)
            case 'break':
                self.builder.branch(self.loop_break_stack[-1])
            case 'continue':
                self.builder.branch(self.loop_continue_stack[-1])
            case 'assign':
                target : tuple = statement[1]
                expression : tuple = statement[2]
                value : ir.Value = self.compile_expression(expression)
                if isinstance(target, str):
                    if target not in self.variables:
                        raise NameError(f'Variable {target} is not declared')
                    pointer : ir.AllocaInstr = self.variables[target][0]
                    if pointer.type.pointee != value.type:
                        if pointer.type.pointee.is_pointer and value.type.is_pointer:
                            value = self.builder.bitcast(value, pointer.type.pointee)
                        else:
                            raise TypeError(f'Type mismatch in assignment to {target} expected {pointer.type.pointee} and got {value.type}')
                    self.safe_store(value, pointer)
                elif isinstance(target, tuple) and target[0] == 'get_attr':
                    object_expression = target[1]
                    field_name = target[2]
                    field_pointer = self.get_field_pointer_general(object_expression, field_name)
                    if field_pointer.type.pointee != value.type:
                        if field_pointer.type.pointee.is_pointer and value.type.is_pointer:
                            value = self.builder.bitcast(value, field_pointer.type.pointee)
                        else:
                            raise TypeError(f'Type mismatch in assignment to field {field_name} expected {field_pointer.type.pointee} and got {value.type}')
                    self.safe_store(value, field_pointer)
                else:
                    raise NotImplementedError(f'Assignment target {target} not implemented')
            case 'class':
                self.compile_class(statement)

    def compile_expression(self, expression:tuple) -> Union[ir.Value, Any]:
        kind : str = expression[0]
        match kind:
            case 'call':
                name : str = expression[1]
                arguments = expression[2]
                argument_values : list[ir.Value] = [self.compile_expression(argument) for argument in arguments]
                if name in self.compiler_data.class_bodies:
                    info = self.compiler_data.class_bodies[name]
                    object_type = info['struct']
                    object_pointer : ir.AllocaInstr = self.builder.alloca(object_type)
                    init_name : str = '_init'
                    init_function_name : str = f'{name}_{init_name}'
                    init_function = self.module.globals.get(init_function_name)
                    if init_function is None:
                        argument_types_llvm = [object_pointer.type] + [argument_value.type for argument_value in argument_values]
                        init_function_type = ir.FunctionType(ir.VoidType(), argument_types_llvm)
                        init_function = ir.Function(self.module, init_function_type, name=init_function_name)
                    self.builder.call(init_function, [object_pointer] + argument_values)
                    return object_pointer
                else:
                    func : ir.Function = self.module.globals.get(name)
                    if not func:
                        function_type : ir.FunctionType = ir.FunctionType(TypeEnum.void, arg_values)
                        func : ir.Function = ir.Function(self.module, function_type, name=name)
                    return self.builder.call(func, argument_values)
            case 'call_method':
                object_expression, method, arguments = expression[1], expression[2], expression[3]
                if isinstance(object_expression, tuple) and object_expression[0] == 'var':
                    object_name = object_expression[1]
                    if object_name in self.variables:
                        object_pointer, object_type = self.variables[object_name]
                        class_name = getattr(getattr(object_type, 'pointee', None), 'name', None)
                        if not class_name:
                            raise RuntimeError(f'Object {object_name} does not have a valid class type')
                        mangled_name: str = f'{class_name}_{method}'
                        func = self.module.globals.get(mangled_name)
                        if not func:
                            raise NameError(f'Method {mangled_name} not found in module')
                        call_arguments = [object_pointer] + [self.compile_expression(argument) for argument in arguments]
                        return self.builder.call(func, call_arguments)
                    elif (object_name in self.extern_c):
                        module_name = object_name
                        full_name = f'{module_name}.{method}'
                        if full_name not in self.extern_functions:
                            raise NameError(f'Extern function {full_name} not found')
                        overloads = self.extern_functions[full_name]
                        argument_values = [self.compile_expression(argument) for argument in arguments]
                        argument_types = tuple(ir_to_string(argument.type) for argument in argument_values)
                        if argument_types not in overloads:
                            raise TypeError(f'Function {full_name} has no overload matching argument types {argument_types}')
                        llvm_name, return_type_id = overloads[argument_types]
                        return_type: ir.Type = string_to_ir(return_type_id)
                        if return_type_id.startswith('list'):
                            return_type = self.list_struct_type.as_pointer()
                        func: Optional[ir.Function] = self.module.globals.get(llvm_name)
                        if not func:
                            func_type: ir.FunctionType = ir.FunctionType(return_type, [argument.type for argument in argument_values])
                            func = ir.Function(self.module, func_type, name=llvm_name)
                        return self.builder.call(func, argument_values)
                    elif object_name in self.extern_modules.keys():
                        module : ir.Module = self.extern_modules[object_name]
                        mangled_name : str = f'{object_name}_{method}'
                        func: Optional[ir.Function] = module.globals.get(mangled_name)
                        if not func:
                            raise NameError(f'Method {mangled_name} not found in module {object_name}')
                        call_arguments = [self.compile_expression(argument) for argument in arguments]
                        return self.builder.call(func, call_arguments)
                elif object_expression == ('this',):
                    object_pointer, object_type = self.variables['this']
                    class_name = getattr(getattr(object_type, 'pointee', None), 'name', None)
                    if not class_name:
                        raise RuntimeError(f'\'this\' does not have a valid class type')
                    mangled_name: str = f'{class_name}_{method}'
                    func = self.module.globals.get(mangled_name)
                    if not func:
                        raise NameError(f'Method {mangled_name} not found in module')
                    call_arguments = [object_pointer] + [self.compile_expression(argument) for argument in arguments]
                    return self.builder.call(func, call_arguments)
                raise NameError(f'Undefined object or module: {object_expression}')
            case 'int':
                return ir.Constant(TypeEnum.int32, expression[1])
            case 'float':
                return ir.Constant(TypeEnum.float32, expression[1])
            case 'string':
                data : bytearray = bytearray(expression[1].encode('utf8') + b'\0')
                string_type : ir.ArrayType = ir.ArrayType(ir.IntType(8), len(data))
                global_string : ir.GlobalVariable = ir.GlobalVariable(self.module, string_type, name=f'string_{len(self.module.global_values)}')
                global_string.global_constant = True
                global_string.initializer = ir.Constant(string_type, data)
                pointer = self.builder.bitcast(global_string, TypeEnum.string)
                return pointer
            case 'binop':
                operator, left_part, right_part = expression[1], expression[2], expression[3]
                left_value = self.compile_expression(left_part)
                right_value = self.compile_expression(right_part)
                match operator:
                    case '==':
                        if left_value.type == TypeEnum.string and right_value.type == TypeEnum.string:
                            llvm_name: str = 'core_string_equal'
                            func : ir.Function = self.module.globals.get(llvm_name)
                            if not func:
                                func = ir.Function(self.module, ir.FunctionType(TypeEnum.boolean, [TypeEnum.string, TypeEnum.string]), name=llvm_name)
                            return self.builder.call(func, [left_value, right_value])
                        return self.builder.icmp_signed('==', left_value, right_value)
                    case '!=':
                        return self.builder.icmp_signed('!=', left_value, right_value)
                    case '<=':
                        return self.builder.icmp_signed('<=', left_value, right_value)
                    case '>=':
                        return self.builder.icmp_signed('>=', left_value, right_value)
                    case '<':
                        return self.builder.icmp_signed('<', left_value, right_value)
                    case '>':
                        return self.builder.icmp_signed('>', left_value, right_value)
                    case '+':
                        if left_value.type == TypeEnum.string and right_value.type == TypeEnum.string:
                            llvm_name: str = 'core_string_concat'
                            func : ir.Function = self.module.globals.get(llvm_name)
                            if not func:
                                func = ir.Function(self.module, ir.FunctionType(TypeEnum.string, [TypeEnum.string, TypeEnum.string]), name=llvm_name)
                            return self.builder.call(func, [left_value, right_value])
                        return self.builder.add(left_value, right_value)
                    case '-':
                        return self.builder.sub(left_value, right_value)
                    case '*':
                        return self.builder.mul(left_value, right_value)
                    case '/':
                        return self.builder.sdiv(left_value, right_value)  # signed division
                    case '%':
                        return self.builder.srem(left_value, right_value)  # signed mod
                    case 'and':
                        return self.builder.and_(left_value, right_value)
                    case 'or':
                        return self.builder.or_(left_value, right_value)
                    case _:
                        raise NotImplementedError(f'Unsupported operator: {operator}')
            case 'unop':
                operator, expression_ = expression[1], expression[2]
                value = self.compile_expression(expression_)
                match operator:
                    case 'not':
                        return self.builder.xor(value, ir.Constant(TypeEnum.boolean, 1))
                    case _:
                        raise NotImplementedError(f'Unsupported unary operator: {operator}')
            case 'var':
                variable_name : str = expression[1]
                if variable_name in self.local_vars:
                    pointer : ir.AllocaInstr = self.local_vars[variable_name]
                    return self.builder.load(pointer)
                elif variable_name in self.variables:
                    pointer : ir.AllocaInstr = self.variables[variable_name][0]
                    return self.builder.load(pointer)
                else:
                    raise NameError(f'Undefined variable: {variable_name}')
            case 'bool':
                return ir.Constant(ir.IntType(1), 1 if expression[1] else 0)
            case 'object_creation':
                _tag, class_name, arguments = expression
                info = self.compiler_data.class_bodies.get(class_name)
                if not info:
                    raise NameError(f'Unknown class {class_name}')
                struct_type : ir.IdentifiedStructType = info['struct']
                object_pointer : ir.AllocaInstr = self.builder.alloca(struct_type)
                init_name : str = '_init'
                constructor_name = f'{class_name}_{init_name}'
                constructor = self.module.globals.get(constructor_name)
                for index, (_tag, _function_type, _function_name, init_expression) in enumerate(info['fields']):
                    if init_expression is not None and not constructor:
                        field_pointer = self.builder.gep(object_pointer, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)])
                        value: ir.Value = self.compile_expression(init_expression)
                        if field_pointer.type.pointee != value.type:
                            value = self.builder.bitcast(value, field_pointer.type.pointee)
                        self.safe_store(value, field_pointer)
                if constructor:
                    argument_values = [self.compile_expression(argument) for argument in arguments]
                    self.builder.call(constructor, [object_pointer] + argument_values)
                return object_pointer
            case 'get_attr':
                object_expression, field_name = expression[1], expression[2]
                if object_expression == ('this',):
                    return self.compile_this_access(field_name)
                if isinstance(object_expression, tuple) and object_expression[0] == 'var':
                    object_name = object_expression[1]
                    object_pointer, object_type = self.variables[object_name]
                    class_name = getattr(getattr(object_type, 'pointee', None), 'name', None)
                    if not class_name:
                        raise RuntimeError(f'Object {object_name} does not have a valid class type')
                    field_pointer: ir.GEPInstr = self.get_field_pointer_general(object_expression, field_name)
                    return self.builder.load(field_pointer)
                raise RuntimeError(f'Unsupported attribute access on {object_expression}')
            case 'postinc' | 'postdec':
                operator : str = kind
                target_expression = expression[1]

                def resolve_pointer_and_type(target_expression_:Union[tuple, str]) -> Union[ir.AllocaInstr, ir.GEPInstr]:
                    if isinstance(target_expression_, tuple) and target_expression_[0] == 'var':
                        variable_name = target_expression_[1]
                        if variable_name not in self.variables:
                            raise NameError(f'Undefined variable: {variable_name}')
                        return self.variables[variable_name][0]
                    if isinstance(target_expression_, tuple) and len(target_expression_) == 1:
                        variable_name = target_expression_[0]
                        if variable_name in self.variables:
                            return self.variables[variable_name][0]
                    if isinstance(target_expression_, tuple) and target_expression_[0] == 'get_attr':
                        object_expression = target_expression_[1]
                        field_name = target_expression_[2]
                        return self.get_field_pointer_general(object_expression, field_name)
                    if isinstance(target_expression_, str):
                        if target_expression_ in self.variables:
                            return self.variables[target_expression_][0]
                    raise NotImplementedError(f'Unsupported target for ++/--: {target_expression_}')

                pointer : Union[ir.AllocaInstr, ir.GEPInstr] = resolve_pointer_and_type(target_expression)
                cur : ir.LoadInstr = self.builder.load(pointer)
                if not isinstance(cur.type, ir.IntType):
                    raise TypeError('++/-- supported only on integer types for now')

                one : ir.Constant = ir.Constant(cur.type, 1)
                new : Any = None
                match operator:
                    case 'postinc':
                        new = self.builder.add(cur, one)
                    case 'postdec':
                        new = self.builder.sub(cur, one)
                self.builder.store(new, pointer)
                return cur
            case _:
                raise NotImplementedError(f'Expresion kind {kind} not implemented')

    def add_c_main(self) -> None:
        function_type : ir.FunctionType = ir.FunctionType(TypeEnum.int32, [])
        main_function : ir.Function = ir.Function(self.module, function_type, name='main')
        block : ir.Block = main_function.append_basic_block(name='entry')
        builder : ir.IRBuilder = ir.IRBuilder(block)
        exec_function = self.module.get_global('_exec')
        return_value = builder.call(exec_function, [])
        builder.ret(return_value)
