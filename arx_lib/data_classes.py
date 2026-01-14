from dataclasses import dataclass, field
from llvmlite import ir
from typing import Any

@dataclass
class TypeEnum:
    int64:ir.IntType = ir.IntType(64)
    int32:ir.IntType = ir.IntType(32)
    int16:ir.IntType = ir.IntType(16)
    int8:ir.IntType  = ir.IntType(8)
    float64:ir.DoubleType = ir.DoubleType()
    float32:ir.FloatType  = ir.FloatType()
    boolean:ir.IntType = ir.IntType(1)
    string:ir.PointerType = ir.IntType(8).as_pointer()
    void:ir.VoidType      = ir.VoidType()

@dataclass
class ArtemisData:
    map_paths:set[str] = field(default_factory=set)
    library_paths:set[str] = field(default_factory=set)
    class_bodies:dict[str, Any] = field(default_factory=dict)
    is_main:bool = False
