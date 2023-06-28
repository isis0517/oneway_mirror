from pypylon import pylon
import numpy as np
import cv2
import os
import json
import datetime
from collections import deque
import tables as tb
import time


class Recorder:
    def __init__(self, fps=30, workpath=""):
        self.is_record = False
        self.frame_num = 0
        self.duration = 0
        self.fps = fps
        self.maxcount = 0
        self.model = "Not init"
        self.workpath = workpath
        self.path = ""
        self.filename = ""
        self._rshape = (10, 10)
        self.img = np.zeros(self._rshape)
        pass

    def setShape(self, rshape: tuple):
        self._rshape = rshape
        if self.img.shape != rshape:
            print(f"{self.model} img not match rshape")

    def setFilename(self, filename: str) -> bool:
        if len(filename) == 0:
            return False
        path = os.path.join(self.workpath, filename)
        if os.path.exists(path):
            s = 0
            while os.path.exists(path + f"({s})"):
                s += 1
            path = path + f"({s})"
        self.filename = filename
        self.path = path
        self.frame_num = -1
        return True

    def setDuration(self, duration):
        self.duration = duration
        self.frame_num = -1
        self.maxcount = self.duration * self.fps

    def dumpConfig(self, config):
        if len(self.path) == 0:
            print(f"{self.model} , no path is used to dump config")
            return

        with open(os.path.join(self.path, "config"), 'w') as file:
            file.write(f"{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}" + "\n")
            json.dump(config, file, indent=4)

    def startRecord(self, filename="", duration=0):
        if len(filename) == 0:
            print(f"{self.model}is not be saved")
            return
        self.setFilename(filename)
        self.setDuration(duration)
        os.mkdir(self.path)
        self.file = tb.open_file(os.path.join(self.path, self.filename+'.h5'), mode='w')
        self.array = self.file.create_earray(self.file.root, 'imgs', tb.UInt8Atom(), (0,)+self._rshape
                                             , expectedrows=self.maxcount)
        self.is_record = True

    def stopRecord(self):
        if self.is_record:
            print(f"{self.model}be stopped, ", self.frame_num)
        self.is_record = False
        self.frame_num = 0
        self.path = ""
        self.filename = ""
        self.maxcount = 0
        try:
            self.file.close()
        except AttributeError as e:
            # print(f"{self.model} no file is saved")
            pass

    def saveFrame(self, img: np.ndarray):
        if not self.is_record:
            return False
        if self.frame_num >= self.maxcount:
            self.is_record = False
            self.stopRecord()
            return False

        if self.frame_num < 0:  # one frame buffer
            self.frame_num += 1
            return True

        self.array.append(img[None, ...])
        self.frame_num += 1
        return True

    def saveImg(self):
        if not self.is_record:
            return False
        if self.frame_num >= self.maxcount:
            self.is_record = False
            self.stopRecord()
            return False

        if self.frame_num < 0: # one frame buffer
            self.frame_num += 1
            return True

        self.array.append(self.img[None, ...])
        self.frame_num += 1
        return True

    def saveBuff(self, buff):
        """
        for RecCam only, at the lag at the buffer frame.
        """
        if not self.is_record:
            return False

        if self.frame_num >= self.maxcount:
            self.is_record = False
            self.stopRecord()
            return False

        if self.frame_num < 0: # one frame buffer
            self.frame_num += 1
            del buff
            time.sleep(2/self.fps)
            return True

        self.array.append(np.ndarray(buffer=buff, shape=(1,)+self._rshape, dtype=self.dtype))
        self.frame_num += 1
        return True


class PygCamera:
    def __init__(self, camera: pylon.InstantCamera, tank_size=np.array([1300, 1300]), fps=30):
        self.model = camera.GetDeviceInfo().GetModelName()
        self.fps = fps
        self.cam_shape, self.dtype = self.camInit(camera)
        self.shape = np.array([self.cam_shape[1], self.cam_shape[0]])  # cv order
        self.camera = camera
        self.tank_shape = tuple((self.shape * min(tank_size / self.shape)).astype(int))  # cv order
        self.delaycount = 0
        self.scenes = deque()
        self.threshold = 40
        self.COM = False
        self.pos = (0, 0)

    def setDelayCount(self, count: int) -> None:
        if self.delaycount == count:
            return
        self.delaycount = count
        lst = [np.zeros((self.tank_shape[1], self.tank_shape[0], 3), dtype=np.uint8)] * count
        self.scenes.clear()
        self.scenes.extend(lst)

    def grabCam(self) -> None:
        try:
            grabResult = self.camera.RetrieveResult(10, pylon.TimeoutHandling_ThrowException)
        except Exception as e:
            return
        if grabResult.GrabSucceeded():
            buff = grabResult.GetBuffer()
            img = cv2.cvtColor(np.ndarray(self.cam_shape, dtype=np.uint8, buffer=buff), cv2.COLOR_BAYER_BG2BGR)
            img = cv2.medianBlur(img, 5)
            img = cv2.resize(img, self.tank_shape, cv2.INTER_LINEAR)
            # gamma = 1  # self.dark_gamma(np.mean(img)/255)
            # lookUpTable = (np.power(np.arange(256) / 255.0, gamma) * 255).astype(np.uint8)
            cv2.convertScaleAbs(img, img, alpha=1.8, beta=-5)

            fg = (np.max(img, axis=2) > self.threshold).astype(np.uint8)
            if self.COM:
                M = cv2.moments(fg)
                if M["m00"] == 0:
                    cX = 0
                    cY = 0
                else:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                cv2.circle(img, (cX, cY), 5, (255, 255, 255), -1)
                self.pos = (cX, cY)
            self.scenes.append(img)
        else:
            print(f"{self.model} camera grab failed at time {datetime.datetime.now()}")
            img = np.ones((self.tank_shape[1], self.tank_shape[0], 3), dtype=np.uint8)
            self.scenes.append(img)

    def update(self) -> np.ndarray:
        self.grabCam()
        return self.scenes.popleft()

    def read(self) -> (bool, np.ndarray):
        self.grabCam()
        if self.scenes:
            img = self.scenes.popleft()
        else:
            return False,  np.ones((self.tank_shape[1], self.tank_shape[0], 3), dtype=np.uint8)

        return True, img

    def garbread(self):
        return True, np.ones((self.tank_shape[0], self.tank_shape[1], 3), dtype=np.uint8)

    def camInit(self, camera: pylon.InstantCamera) -> (np.ndarray, np.dtype):
        if camera.GetDeviceInfo().GetModelName() == "Emulation":
            camera.Open()
            grabResult = camera.GrabOne(6000)
            if grabResult.GrabSucceeded():
                pt = grabResult.GetPixelType()
                if pylon.IsPacked(pt):
                    _, new_pt = grabResult._Unpack10or12BitPacked()
                    shape, dtype, pixelformat = grabResult.GetImageFormat(new_pt)
                else:
                    shape, dtype, pixelformat = grabResult.GetImageFormat(pt)
                    _ = grabResult.GetImageBuffer()
            else:
                raise Exception()

            self.read = self.garbread

            camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            return (shape, dtype)

        camera.Open()

        grabResult = camera.GrabOne(1000)
        if grabResult.GrabSucceeded():
            pt = grabResult.GetPixelType()
            if pylon.IsPacked(pt):
                _, new_pt = grabResult._Unpack10or12BitPacked()
                shape, dtype, pixelformat = grabResult.GetImageFormat(new_pt)
            else:
                shape, dtype, pixelformat = grabResult.GetImageFormat(pt)
                _ = grabResult.GetImageBuffer()

        else:
            print("grab Failed")
            raise Exception('grab failed')
        camera.Open()
        camera.AcquisitionFrameRateEnable.SetValue(True)
        camera.AcquisitionFrameRate.SetValue(self.fps*2)
        camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
        camera.OutputQueueSize = 2

        return shape, dtype

    @staticmethod
    def dark_gamma(brightness):
        return np.log(.007) / np.log(brightness)

    def close(self):
        self.camera.Close()


class RecCamera(Recorder):
    def __init__(self, camera, fps, workpath=""):
        super().__init__(fps=fps, workpath=workpath)
        self.model = camera.GetDeviceInfo().GetModelName()
        self.poses = []
        self.camera = camera
        self.camera.Open()
        grabResult = self.camera.GrabOne(1000)
        if grabResult.GrabSucceeded():
            pt = grabResult.GetPixelType()
            if pylon.IsPacked(pt):
                _, new_pt = grabResult._Unpack10or12BitPacked()
                shape, dtype, pixelformat = grabResult.GetImageFormat(new_pt)
            else:
                shape, dtype, pixelformat = grabResult.GetImageFormat(pt)
                _ = grabResult.GetImageBuffer()
        else:
            print("grab Failed")
            raise Exception('grab failed')
        self.camera.AcquisitionFrameRateEnable.SetValue(True)
        self.camera.AcquisitionFrameRate.SetValue(self.fps)
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
        self.camera.OutputQueueSize = 1
        self.shape = shape
        self.dtype = dtype
        self.setShape(self.shape)


    def updateFrame(self, poses=None):
        grabResult = self.camera.RetrieveResult(1000, pylon.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            self.saveBuff(grabResult.GetBuffer())

        else:
            print(f"{self.model} camera grab failed at time {datetime.datetime.now()}, which mission is recording")

    def __del__(self):
        self.camera.Close()


def getCams():
    try:
        T1 = pylon.TlFactory.GetInstance()
        lstDevices = T1.EnumerateDevices()
        if len(lstDevices) == 0:
            print("no camera is detected")
        cameras = []
        for cam_info in lstDevices:
            cameras.append(pylon.InstantCamera(T1.CreateFirstDevice(cam_info)))

        print("total camera numbers : ",
              len(lstDevices))
    except:
        print("init fail")
        raise Exception("camera init failed")
    return cameras
