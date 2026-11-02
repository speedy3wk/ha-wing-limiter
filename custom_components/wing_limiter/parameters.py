"""Verified COMP parameters from the WING remote protocol, not plugin guesses."""

import math
from dataclasses import dataclass

from .osc import OscValue


@dataclass(frozen=True)
class Parameter:
    key: str
    path: str
    kind: type
    minimum: float = 0
    maximum: float = 0
    step: float = 1
    unit: str | None = None
    options: tuple[str, ...] = ()
    comp_only: bool = True

    def valid(self, value: OscValue | None) -> bool:
        if self.options:
            if self.kind is float and isinstance(value, (int, float)):
                return any(
                    math.isclose(value, float(option), rel_tol=1e-6)
                    for option in self.options
                )
            return str(value) in self.options
        if self.kind is str:
            return isinstance(value, str)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        if not math.isfinite(value):
            return False
        if self.kind is int and value != int(value):
            return False
        return self.minimum <= value <= self.maximum

    def encode(self, value: OscValue) -> OscValue:
        if not self.valid(value):
            raise ValueError(f"Invalid {self.key}: {value}")
        if self.kind is str:
            return str(value)
        return int(value) if self.kind is int else float(value)


NUMBERS = (
    Parameter("comp_thr", "dyn/thr", float, -60, 0, 0.5, "dB"),
    Parameter("comp_gain", "dyn/gain", float, -6, 12, 0.5, "dB"),
    Parameter("comp_mix", "dyn/mix", float, 0, 100, 1, "%"),
    Parameter("comp_att", "dyn/att", float, 0, 120, 1, "ms"),
    Parameter("comp_hld", "dyn/hld", float, 1, 200, 1, "ms"),
    Parameter("comp_rel", "dyn/rel", float, 4, 4000, 0.1, "ms"),
    Parameter("comp_knee", "dyn/knee", int, 0, 5),
    Parameter("sc_f", "dynsc/f", float, 20, 20000, 0.1, "Hz"),
    Parameter("sc_q", "dynsc/q", float, 0.44, 10, 0.01),
)
SELECTS = (
    Parameter(
        "comp_ratio",
        "dyn/ratio",
        float,
        options=(
            "1.1",
            "1.2",
            "1.3",
            "1.5",
            "1.7",
            "2.0",
            "2.5",
            "3.0",
            "3.5",
            "4.0",
            "5.0",
            "6.0",
            "8.0",
            "10.0",
            "20.0",
            "50.0",
            "100.0",
        ),
    ),
    Parameter("comp_det", "dyn/det", str, options=("PEAK", "RMS")),
    Parameter("comp_env", "dyn/env", str, options=("LIN", "LOG")),
    Parameter(
        "sc_type", "dynsc/type", str, options=("OFF", "LP12", "HP12", "BP", "NOTCH")
    ),
    Parameter(
        "sc_src",
        "dynsc/src",
        str,
        options=(
            "SELF",
            *(f"BUS.{n}" for n in range(1, 17)),
            *(f"MAIN.{n}" for n in range(1, 5)),
            *(f"MTX.{n}" for n in range(1, 9)),
            *(f"AUX.{n}" for n in range(1, 9)),
        ),
    ),
    Parameter(
        "sc_tap", "dynsc/tap", str, options=("BUS", "DYN", "PFL", "AFL", "EQ", "INS2")
    ),
)
SWITCHES = (
    Parameter("comp_on", "dyn/on", int, 0, 1, comp_only=False),
    Parameter("comp_auto", "dyn/auto", int, 0, 1),
)
PARAMETERS = {param.key: param for param in (*NUMBERS, *SELECTS, *SWITCHES)}
