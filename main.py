from TKwindows import *
from _util import *
from pyfirmata2 import Arduino
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# to do
# 1. right-left flip image
# 2. saving faster - bug now
# 3. image enhance
# 4. adding random to the path

# abstract the pygame showing layer so that it can change the playing source. And also, let all recorded camera share
# same interface.

if __name__ == "__main__":

    ## this line enable the camera emulater
    os.environ["PYLON_CAMEMU"] = "1"
    # parameter
    bk_color = (200, 200, 200)  # RGB

    # pygame init
    pygame.init()
    pygame.font.init()  # you have to call this at the start,
    # myfont = pygame.font.SysFont('Comic Sans MS', 25)

    # camera init
    cameras = getCams()
    init_window = InitWindows(cameras)
    use_cams = init_window.display_cams
    rec_cams = init_window.rec_cam
    display = init_window.display_num
    workpath = init_window.workpath
    pgFps = init_window.pgFps
    PORT = init_window.port

    # loading arduino
    if PORT == "None":
        PORT = None
    board = Arduino(PORT)

    # pygame config
    pygame.display.set_caption("OpenCV camera stream on Pygame")
    pgClock = pygame.time.Clock()
    flags = 0  # pygame.RESIZABLE  # | pygame.DOUBLEBUF | pygame.SCALED  pygame.NOFRAME | #  #pygame.HWSURFACE | pygame.FULLSCREEN pygame.RESIZABLE ||
    #     # pygame.HWSURFACE | pygame.DOUBLEBUF
    flags = flags | pygame.SHOWN | pygame.DOUBLEBUF | pygame.HWSURFACE | pygame.NOFRAME  # | pygame.FULLSCREEN
    init_size = [0, 0]

    # stage init
    screen = pygame.display.set_mode(init_size, display=display, flags=flags)
    screen.fill([0, 0, 0])
    pygame.display.update()
    sc_shape = pygame.display.get_window_size()

    # PygCam setting
    pyg_stages = []
    for cam in use_cams:
        pyg_stages.append(TankStage(PygCamera(cam, fps=pgFps), sc_shape, workpath=workpath))

    # console setting
    console = Console([obj.pycamera.model for obj in pyg_stages])
    console.start()
    console.send({"center": [obj.center for obj in pyg_stages]})

    # loop init
    is_running = True
    is_display = True
    able_record = False
    is_sidesave = False
    send_cam = -1
    counter = 0

    # rect config
    tank_sel = False
    m_pos = (0, 0)
    setDisplace = lambda x: None

    # rec config
    pglock = pgFps
    if rec_cams is not None:
        recorder = RecCamera(rec_cams, pgFps, workpath=workpath)
        able_record = True
        pglock = 0

    # loop start
    while is_running and console.is_alive():

        # the rects will be updated, it is the key point to take fps stable
        rects = []

        # all keyboard event is detected here
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                is_running = False

            # mouse button down, check whether the tank image is selected.
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for obj in reversed(pyg_stages):
                    cover = obj.getCover()
                    if cover.collidepoint(pygame.mouse.get_pos()):
                        tank_sel = True
                        # assign the displace function.
                        setDisplace = obj.setDisplace
                        break
                m_pos = pygame.mouse.get_pos()

            # mouse button release, no tank is select
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                tank_sel = False
                console.send({"center": [obj.center for obj in pyg_stages]})

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    # Q -> kill the process
                    is_running = False

        # console trigger
        if console.poll():   # if console set some values
            config = console.getConfig()
            is_running = config['is_running']

            for s, obj in enumerate(pyg_stages):
                if not config['cams'][s]['model'] == obj.pycamera.model:
                    print(f"waring, The config may wrong, the config for {config['cams'][s]['model']} is trying to apply"
                          f" on camera {obj.pycamera.model}")
                config['cams'][s] = obj.setConfig(config['cams'][s])
            console.send({"center": [obj.center for obj in pyg_stages], "vpath": [obj.video.path for obj in pyg_stages]
                          , "sdir": [obj.filename for obj in pyg_stages]})

            is_display = config["display"] == 1
            if config["light"] == 1:
                board.digital[12].write(1)
            else:
                board.digital[12].write(0)

            if 'is_record' in config:
                if config['is_record']:
                    if able_record:
                        recorder.startRecord(filename=config['folder'], duration=config['duration'])
                        recorder.dumpConfig(config)
                    for s, obj in enumerate(pyg_stages):
                        obj.startRecord(filename=config['cams'][s]['sdir'], duration=config['duration'])
                else:
                    if able_record:
                        recorder.stopRecord()
                    for s, obj in enumerate(pyg_stages):
                        obj.stopRecord()

            send_cam = config["debug_cam"]

            if 'bk_color' in config:
                c = config['bk_color']
                bk_color = (c, c, c)

            rects.append(screen.fill([0, 0, 0]))
            # update the value

        # update the pos
        if tank_sel:
            rects.append(screen.fill([0, 0, 0]))
            c_pos = pygame.mouse.get_pos()
            setDisplace((c_pos[0]-m_pos[0], c_pos[1]-m_pos[1]))
            m_pos = c_pos

        # update the screen
        for obj in pyg_stages:
            obj.saveImg()   # saving first, due to the one frame buffer
            frame = obj.updateFrame()
            screen.blit(frame, obj)
            rects.append(obj)
            rects.append(pygame.draw.rect(screen, bk_color, obj.background))

        if not is_display:
            rects.append(screen.fill([0, 0, 0]))

        # stage update here
        pygame.display.update(rects)
        pgClock.tick(pglock)

        if send_cam >= 0:
            console.send({"img": pyg_stages[send_cam].img})

        counter += 1
        if counter == pgFps:
            console.send({"fps": pgClock.get_fps()})
            counter = 0

        if able_record:
            recorder.updateFrame()

    pygame.quit()
    for obj in pyg_stages:
        obj.pycamera.camera.Close()
    if console.is_alive():
        console.terminate()

