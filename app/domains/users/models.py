from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Usuario(ABC):
    nombre: str
    codigo: str
    carrera: str

    @property
    @abstractmethod
    def tipo(self) -> str: ...


@dataclass
class Alumno(Usuario):
    ciclo_actual: int
    creditos: int

    @property
    def tipo(self) -> str:
        return "alumno"


@dataclass
class Profesor(Usuario):

    @property
    def tipo(self) -> str:
        return "profesor"
