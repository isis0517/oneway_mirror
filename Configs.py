from typing import TypedDict, List


class CamConfig(TypedDict, total=False):
    model: str
    threshold: int
    lag: float
    com: bool  # center of mass


class RecordConfig(TypedDict, total=False):
    folder: str
    duration: int
    fps: int


class TankConfig(TypedDict, total=False):
    show: int
    center: str
    vpath: str
    sdir: str


class CamStageConfig(CamConfig, TankConfig, total=False):
    pass


class ConsoleConfig(RecordConfig, total=False):
    light: bool
    display: bool
    is_record: bool
    debug_cam: int
    is_running: bool
    break_sec: int
    bk_color: int
    cams: List[CamStageConfig]