import os.path
import re
from Cameras import *
from Configs import *
from typing import Union
import tables as tb
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

class VideoLoader:
    def __init__(self, cv_shape):
        self.cv_shape = cv_shape
        self.source = 0 # 0: npy, 1: cv2, 2: h5
        self.path = ""
        self.itr = iter([])
        self.file = None
        self.itarray = iter([0])

    def releaseSource(self):
        if self.source == 0:
            self.path = ""
            self.itr = iter([])
        if self.source == 1:
            self.video.release()
        if self.source == 2:
            self.file.close()
            self.itarray = iter([0])
        self.source = 0

    def setPath(self, path: str) -> bool:
        self.releaseSource()
        try:
            if os.path.exists(path):
                if os.path.isdir(path):
                    flist = list(filter(lambda x: "npy" in x, os.listdir(path)))
                    if len(flist) < 10:
                        return False
                    self.source = 0
                    flist.sort(key=lambda x: (int(re.findall('[0-9]+', x)[0])))
                    self.itr = flist.__iter__()
                    self.path = path
                    return True

                elif os.path.isfile(path):
                    if path.find(".mp4") > 0 or path.find(".avi") > 0:
                        self.source = 1
                        self.video = cv2.VideoCapture(path)
                        self.path = path
                        return True

                    if path.find(".h5") > 0:
                        self.source = 2
                        self.file = tb.open_file(path, 'r')
                        self.path = path
                        for node in self.file:
                            obj = self.file.get_node(node)
                            if isinstance(obj, tb.array.Array):
                                if isinstance(obj.atom, tb.UInt8Atom):
                                    self.itarray = obj.__iter__()
                        return True
                    return False
            return False
        except Exception as e:
            print(e)
            return False

    def read(self) -> (bool, np.ndarray):
        if self.source == 0:
            try:
                name = next(self.itr)
                img = np.load(os.path.join(self.path, name))
                return True, cv2.resize(img, self.cv_shape)
            except StopIteration as e:
                pass

        elif self.source == 1:
            ret, img = self.video.read()
            if ret:
                return True, cv2.resize(img, self.cv_shape)
            else:
                self.releaseSource()

        elif self.source == 2:
            try:
                img = self.itarray.__next__()
                return True, cv2.resize(img, self.cv_shape)
            except StopIteration as e:
                self.releaseSource()
                pass

        return False, np.ones((self.cv_shape[1], self.cv_shape[0], 3), dtype=np.uint8)


class TankStage(pygame.Rect, Recorder):
    def __init__(self, camera: PygCamera, sc_shape: Union[tuple, np.ndarray], workpath=""):
        self.pycamera = camera
        pygame.Rect.__init__(self, (0, 0), tuple(self.pycamera.tank_shape))
        Recorder.__init__(self, workpath=workpath)
        self.config = CamStageConfig(model=self.pycamera.model)
        self.model = self.pycamera.model
        self.center = (sc_shape[0] - self.pycamera.tank_shape[0] // 2, sc_shape[1] -self.pycamera.tank_shape[1] // 2)
        self.tank_shape = self.pycamera.tank_shape
        self.background = self.copy()
        self.background.height = 1000
        self.background.bottomleft = self.topleft

        self.video = VideoLoader(self.tank_shape)
        self.is_video = False

        self.is_show = True
        self.is_flip = False

        self.img = np.zeros((self.tank_shape[1], self.tank_shape[0], 3), dtype=np.uint8)
        self.fps = self.pycamera.fps

        self.setShape(self.img.shape)

    def getCover(self) -> pygame.Rect:
        return self.union(self.background)

    def setDisplace(self, dis: tuple) -> None:
        self.move_ip(dis)
        self.background.bottomleft = self.topleft
        self.config['center'] = self.center.__str__()

    def setSource(self, path: str) -> bool:
        self.is_video = False
        if self.video.setPath(path):
            print(f"{self.model} load video: {path}, ")
            self.is_video = True
            self.config['vpath'] = path
            return True
        else:
            print(f"{path} not exist")
            return False

    def setConfig(self, config: Union[CamStageConfig, TankConfig]) -> dict:
        if config["show"] == 1:
            self.is_show = True
            self.is_flip = False
        elif config['show'] == 2:
            self.is_show = True
            self.is_flip = True
        else:
            self.is_show = False
        if config["com"] == 1:
            self.pycamera.COM = True
        else:
            self.pycamera.COM = False

        lag = config["lag"]
        self.pycamera.threshold = config["threshold"]
        lag_frame = lag*self.fps
        if not lag_frame == int(lag_frame):
            print(f"Warning, the {self.model} got the not frame saved lag setting. lag = {lag} sec "
                  f"but the frame delay = {lag_frame}")
        lag_frame = int(lag_frame)
        self.pycamera.setDelayCount(lag_frame)

        if 'center' in config:
            try:
                center = config['center']
                center_sparse = center[center.index("(") + 1:center.index(")")].split(",")
                center = (int(center_sparse[0]), int(center_sparse[1]))
                if center[0] < 0 or center[1] < 0:
                    raise Exception()
                if len(center) > 2:
                    raise Exception()
                self.center = center
                self.background.bottomleft = self.topleft
            except Exception as e:
                pass
            config['center'] = self.center.__str__()

        if 'vpath' in config:
            if self.setSource(config['vpath']):
                pass
            else:
                config["vpath"] = ""
        self.config = config

        if 'sdir' in config:
            if len(self.filename) == 0:
                self.setFilename(config['sdir'])

        return self.config

    def updateFrame(self) -> pygame.surface:

        if not self.is_show:
            return pygame.image.frombuffer(bytearray(self.tank_shape[0]*self.tank_shape[1]*3), self.tank_shape, 'RGB')

        if self.is_video:
            ret, self.img = self.video.read()
            if not ret:
                print("is end of the video")
                self.is_video = False
                self.config['vpath'] = ""
            return pygame.image.frombuffer(self.img.tobytes(), self.tank_shape, 'RGB')

        ret, img = self.pycamera.read()

        if self.is_flip:
            img = np.flip(img, axis=1)

        if not ret:
            return pygame.image.frombuffer(self.img.tobytes(), self.tank_shape, 'RGB')
        self.img = img

        return pygame.image.frombuffer(self.img.tobytes(), self.tank_shape, 'RGB')


class Logger:
    def __init__(self, rootpath):
        self.rootpath = rootpath
        self.file = open(os.path.join(rootpath, "mm_log"), 'w')
        self.headers = []

    def log(self, mes):
        time_stamp = datetime.datetime.now().strftime("%Y/%d/%m %H:%M:%S ")
        self.file.write(time_stamp+mes)

    def __del__(self):
        self.file.close()

