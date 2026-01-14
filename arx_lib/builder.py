from .lexer import ArtemisLexer
from .parser import ArtemisParser
from .compiler import ArtemisCompiler
from .data_classes import ArtemisData
from .helpers import debug_print

import os, sys, subprocess, shutil, platform
from typing import Optional

is_windows : bool = os.name == 'nt'

def build(file_in:str, executable_dir:str) -> None:
    map_paths : set[str] = set()
    map_paths.add(os.path.join(executable_dir, 'c_map'))
    compiler_data : ArtemisData = ArtemisData(map_paths)
    compiler_data.is_main = True
    compiler : ArtemisCompiler = ArtemisCompiler(compiler_data)
    module : str = compiler.compile_exec(file_in)

    llc_path : Optional[str] = shutil.which('llc')
    gcc_path : Optional[str] = shutil.which('gcc')

    if (not llc_path):
        raise EnvironmentError('Make sure (llc) is installed and on your PATH.')
    if (not gcc_path):
        raise EnvironmentError('Make sure (gcc) is installed and on your PATH.')

    os.makedirs(os.path.join(executable_dir, 'build'), exist_ok=True)
    os.makedirs(os.path.join(executable_dir, 'out'), exist_ok=True)

    object_extension : str = '.obj' if is_windows else '.o'
    out_ll : str = os.path.join(executable_dir, 'build', os.path.basename(file_in).rsplit('.', 1)[0] + '.ll')
    out_o : str = out_ll.rsplit('.', 1)[0] + object_extension
    with open(out_ll, 'w') as f:
        f.write(module)
    debug_print('[llc]')
    subprocess.run([llc_path, out_ll, '-filetype=obj', '-o', out_o], check=True)

    final_command : list[str] = [gcc_path, out_o]
    total_libs : int = len(compiler.extern_c) + 1
    for i, c_lib in enumerate(compiler.extern_c):
        print(f'[ {i + 1}/{total_libs} ]' + ' [lib] (' + c_lib + ')')
        subprocess.run([gcc_path, '-c', '-o', os.path.join(executable_dir, 'build', c_lib + object_extension), os.path.join(executable_dir, 'c_lib', c_lib + '.c')], check=True)
        final_command.append(
            os.path.join(executable_dir, 'build', c_lib + object_extension)
        )
    print(f'[ {total_libs}/{total_libs} ]' + ' [main]')
    out_executable : str = os.path.join(executable_dir, 'out', os.path.basename(file_in).rsplit('.', 1)[0] + ('.exe' if is_windows else ''))
    subprocess.run(final_command + ['-o', out_executable], check=True)
    print(f'Built at [ {out_executable} ]')
