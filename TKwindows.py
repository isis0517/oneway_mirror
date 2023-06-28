import screeninfo
from Configs import *
import json
import time
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox
from multiprocessing import Pipe, Process
import os
import cv2
from pyfirmata2 import Arduino
from tkinter.filedialog import asksaveasfile, askopenfilename
import datetime
import copy

class InitWindows(tk.Frame):
    def __init__(self, cameras):
        self.root = tk.Tk()
        # self.root.geometry('500x300')
        tk.Frame.__init__(self, self.root)
        combo_values = ["Record", "Display", "No Use"]
        row_num = 0
        self.cameras = cameras
        self.cam_usage = list()
        self.cam_prompts = list()
        for camera in self.cameras:
            self.cam_prompts.append(tk.Label(self, text=camera.GetDeviceInfo().GetModelName(), anchor='w'))
            self.cam_usage.append(ttk.Combobox(self, values=combo_values, width=7))
            self.cam_prompts[-1].grid(column=0, row=row_num, sticky="W")
            self.cam_usage[-1].grid(column=1, row=row_num, sticky="W")
            self.cam_usage[-1].current(2)
            row_num += 1

        default_path = os.getcwd()
        if os.path.isdir("D:/"):
            default_path = r"D:/"
        self.path_prompt = tk.Label(self, text="Working dictionary : ")
        self.path_prompt.grid(column=0, row=row_num, sticky="W")
        self.path_entry = tk.Entry(self, text=0, width=40)
        self.path_entry.insert(tk.END, default_path)
        self.path_entry.grid(column=1, row=row_num, sticky="W")
        row_num += 1

        monitors = screeninfo.get_monitors()
        self.display_prompt = tk.Label(self, text="pygame display numbers:")
        self.display_prompt.grid(column=0, row=row_num, sticky="W")
        self.display_combo = ttk.Combobox(self, values=[f"{s} ({m.width}x{m.height})" for s, m in enumerate(monitors)]
                                          , width=12)
        self.display_combo.current(max(range(len(monitors)), key=lambda x: monitors[x].height))
        self.display_combo.grid(column=1, row=row_num, sticky="W")
        row_num += 1

        self.pgFps_prompt = tk.Label(self, text="pygame frame rate:")
        self.pgFps_prompt.grid(column=0, row=row_num, sticky="W")
        self.pgFps_entry = tk.Entry(self, width=5)
        self.pgFps_entry.insert(tk.END, 30)
        self.pgFps_entry.grid(column=1, row=row_num, sticky="W")
        row_num += 1

        self.arport_prompt = tk.Label(self, text="Arduino port")
        self.arport_prompt.grid(column=0, row=row_num, sticky="W")
        self.arport_entry = tk.Entry(self, width=5)
        self.arport_entry.insert(tk.END, str(Arduino.AUTODETECT))
        self.arport_entry.grid(column=1, row=row_num, sticky="W")
        row_num += 1

        self.check_btn = tk.Button(self, text="Check", command=self.check, width=10, heigh=2)
        self.check_btn.grid(column=0, row=row_num, columnspan=2)
        self.pack(fill="both", expand=True)

        self.root.mainloop()

    def check(self):
        self.rec_cam = None
        self.display_cams = []
        for c_num, usage in enumerate(self.cam_usage):
            if usage.current() == 0:
                self.rec_cam = self.cameras[c_num]
            elif usage.current() == 1:
                self.display_cams.append(self.cameras[c_num])

        self.display_num = int(self.display_combo.current())
        self.workpath = self.path_entry.get()
        self.pgFps = int(self.pgFps_entry.get())
        self.port = self.arport_entry.get()
        self.root.destroy()


class ConfigWindow(tk.Frame):
    def __init__(self, conn_recv, conn_send, init_cams):
        self.root = tk.Tk()
        self.init_cams = init_cams
        self.conn_recv = conn_recv
        self.conn_send = conn_send
        self.start = 0
        self.fps = 0
        super().__init__(self.root)

        self.config = ConsoleConfig(is_record=False, is_running=True, debug_cam=-1, light=True, display=True, cams=[]
                                    , bk_color=200)
        self.console_dict = {"state": "idle"}
        self.root.title('console panel')

        # =================stage start ===============================
        self.stage_frame = ttk.Frame(borderwidth=2, relief='solid')
        self.stage_frame.pack(anchor='center')

        self.stage_title = tk.Label(self.stage_frame, text="Stage config", font=('Arial', 12), width=20, height=2, anchor='center')
        self.stage_title.grid(column=0, row=0, columnspan=7)

        self.stage_column = ["cam model", "show", "lag", "COM", "threshold", "center", "video path", "save folder"]
        self.stage_col_labels = []
        for col_num, text in enumerate(self.stage_column):
            self.stage_col_labels.append(tk.Label(self.stage_frame, text=text, anchor='center'))
            self.stage_col_labels[-1].grid(column=col_num, row=1)

        row_num = 2
        self.stage_cam_labels = []
        self.stage_show_combos = []
        self.stage_lag_entrys = []
        self.stage_com_vars = []
        self.stage_threshold_entrys = []
        self.stage_center_entrys = []
        self.stage_vpath_entrys = []
        self.stage_sdir_entrys = []

        for s, cam in enumerate(self.init_cams):
            self.config['cams'].insert(s, CamStageConfig(model=cam, lag=0, com=False, threshold=0, center="", vpath="", show=True))
            self.stage_cam_labels.append(tk.Label(self.stage_frame, text=cam, anchor='w'))
            self.stage_cam_labels[-1].grid(column=0, row=row_num)

            self.stage_show_combos.append(ttk.Combobox(self.stage_frame, values=['None', 'mirror', 'inter'], width=6))
            self.stage_show_combos[-1].grid(column=1, row=row_num)
            self.stage_show_combos[-1].current(1)

            self.stage_lag_entrys.append(tk.Entry(self.stage_frame, width=3))
            self.stage_lag_entrys[-1].grid(column=2, row=row_num)
            self.stage_lag_entrys[-1].insert(tk.END, "0")

            self.stage_com_vars.append(tk.IntVar(self.root))
            checkbox = ttk.Checkbutton(self.stage_frame, variable=self.stage_com_vars[-1])
            checkbox.grid(column=3, row=row_num)

            self.stage_threshold_entrys.append(tk.Entry(self.stage_frame, width=4))
            self.stage_threshold_entrys[-1].grid(column=4, row=row_num)
            self.stage_threshold_entrys[-1].insert(tk.END, "0")

            self.stage_center_entrys.append(tk.Entry(self.stage_frame, width=12))
            self.stage_center_entrys[-1].grid(column=5, row=row_num)
            self.stage_center_entrys[-1].insert(tk.END, "0, 0")

            self.stage_vpath_entrys.append(tk.Entry(self.stage_frame, width=12))
            self.stage_vpath_entrys[-1].grid(column=6, row=row_num)
            self.stage_vpath_entrys[-1].insert(tk.END, "")

            self.stage_sdir_entrys.append(tk.Entry(self.stage_frame, width=12))
            self.stage_sdir_entrys[-1].grid(column=7, row=row_num)
            self.stage_sdir_entrys[-1].insert(tk.END, "")

            row_num += 1

        self.stage_display_var = tk.IntVar(self.root)
        self.stage_display_var.set(1)
        self.stage_light_var = tk.IntVar(self.root)
        self.stage_light_var.set(1)
        checkbox = ttk.Checkbutton(self.stage_frame, variable=self.stage_display_var, text="display")
        checkbox.grid(column=4, row=row_num)
        checkbox = ttk.Checkbutton(self.stage_frame, variable=self.stage_light_var, text="light")
        checkbox.grid(column=5, row=row_num)
        label = tk.Label(self.stage_frame, text="bg intens")
        label.grid(column=6, row=row_num, sticky='w')
        self.stage_color_entry = tk.Entry(self.stage_frame, width=3)
        self.stage_color_entry.insert(tk.END, str(200))
        self.stage_color_entry.grid(column=6, row=row_num, sticky='e')

        self.stage_set_but = tk.Button(self.stage_frame, text="SET", command=self.stage_butf_set, heigh=1, width=6
                                       , font=('Arial Bold', 12))
        self.stage_set_but.grid(column=7, row=row_num)

        # =================exp start ===============================
        self.exp_frame = ttk.Frame(borderwidth=2, relief='solid')
        self.exp_frame.pack(anchor='center')

        self.exp_title = tk.Label(self.exp_frame, text="Experiment", font=('Arial', 12), width=10, height=2
                                  , anchor='center')
        self.exp_title.grid(column=0, row=0, columnspan=5)

        self.exp_break_label = tk.Label(self.exp_frame, text="Break time (sec)")
        self.exp_break_label.grid(column=0, row=1)
        self.exp_break_entry = tk.Entry(self.exp_frame)
        self.exp_break_entry.insert(tk.END, "300")
        self.exp_break_entry.grid(column=1, row=1)

        self.exp_duration_label = tk.Label(self.exp_frame, text="Duration (sec)")
        self.exp_duration_label.grid(column=0, row=2)
        self.exp_duration_entry = tk.Entry(self.exp_frame)
        self.exp_duration_entry.insert(tk.END, "600")
        self.exp_duration_entry.grid(column=1, row=2)

        self.exp_filename_label = tk.Label(self.exp_frame, text="Saving name")
        self.exp_filename_label.grid(column=0, row=3)
        self.exp_filename_entry = tk.Entry(self.exp_frame)
        self.exp_filename_entry.insert(tk.END, "exp")
        self.exp_filename_entry.grid(column=1, row=3)

        self.exp_add_but = tk.Button(self.exp_frame, text="ADD", command=self.exp_butf_add)
        self.exp_add_but.grid(column=5, row=10)

        self.exp_dump_but = tk.Button(self.exp_frame, text="Dump", heigh=1, command=self.exp_butf_dump)
        self.exp_dump_but.grid(column=0, row=10, sticky='w')

        # =================schedule start ===============================
        self.schedule_frame = ttk.Frame(self.root, borderwidth=2, relief='solid')
        self.schedule_frame.pack()

        self.schedule_title = tk.Label(self.schedule_frame, text="Schedule", font=('Arial', 12))
        self.schedule_title.grid(column=0, row=0, columnspan=5)

        self.schedule_columns = ["num", "sec", "folder", "state"]
        self.schedule_col_labels = []
        for col_num, text in enumerate(self.schedule_columns):
            self.schedule_col_labels.append(tk.Label(self.schedule_frame, text=text, width=10, anchor='center'))
            self.schedule_col_labels[-1].grid(column=col_num, row=1)

        self.schedule_config_lst = []
        self.schedule_label_lst = []
        self.schedule_state_labels = []
        self.schedule_event_lst = []
        self.schedule_state = {"num": 0}

        self.schedule_remove_comb = ttk.Combobox(self.schedule_frame, values=["None", "ALL"], width=4)
        self.schedule_remove_comb.grid(column=2, row=10)

        self.schedule_remove_but = tk.Button(self.schedule_frame, text="remove", heigh=1, command=self.schedule_butf_remove)
        self.schedule_remove_but.grid(column=3, row=10)

        self.schedule_go_but = tk.Button(self.schedule_frame, text="GO", heigh=1, font=('Arial Bold', 12), command=self.schedule_butf_go)
        self.schedule_go_but.grid(column=4, row=10)

        self.schedule_stop_but = tk.Button(self.schedule_frame, text="STOP", heigh=1, font=('Arial Bold', 12), command=self.schedule_butf_stop)
        self.schedule_stop_but.configure(state="disable")
        self.schedule_stop_but.grid(column=0, row=10)

        self.schedule_save_but = tk.Button(self.schedule_frame, text="save", heigh=1, font=('Arial Bold', 12),
                                           command=self.schedule_butf_save)
        self.schedule_save_but.grid(column=2, row=11)

        self.schedule_load_but = tk.Button(self.schedule_frame, text="load", heigh=1, font=('Arial Bold', 12),
                                           command=self.schedule_butf_load)
        self.schedule_load_but.grid(column=3, row=11)

        self.exp_current_label = tk.Label(self.root)
        self.exp_current_label.pack(side='right', fill=tk.BOTH)

        # =================debug start ===============================
        self.debug_frame = ttk.Frame(self.root, borderwidth=2, relief='solid', width=100)
        self.debug_frame.pack(side='left', fill=tk.BOTH)

        self.debug_label = tk.Label(self.debug_frame, text="debug camera:")
        self.debug_label.grid(column=0, row=0)

        self.debug_camera_combo = ttk.Combobox(self.debug_frame, values=["None"] + self.init_cams, width=7)
        self.debug_camera_combo.current(0)
        self.debug_camera_combo.grid(column=1, row=0)

        self.debug_camera_combo.bind("<<ComboboxSelected>>", self.debug_combf_select)
        self.root.protocol("WM_DELETE_WINDOW", self.root_close)

        # 第6步，主視窗迴圈顯示
        self.exp_setting()
        self.stage_setting()
        self.send_config()
        self.root.after(10, self.update)
        self.root.mainloop()

    def breaking(self):
        self.schedule_state_labels[self.schedule_state["num"]]['text'] = "break"
        self.console_dict['state'] = "breaking"
        self.config['display'] = False
        self.config['light'] = False
        self.show_stage(self.config)
        self.send_config()

    def recording(self):
        """
        turn on the light and go record
        """
        self.schedule_state_labels[self.schedule_state["num"]]['text'] = "record"
        self.config['display'] = True
        self.config['light'] = True
        self.console_dict['state'] = "recording"
        self.config["is_record"] = True
        self.send_config()

    def done(self):
        self.config["is_record"] = False
        self.send_config()

    def end_exp(self):
        self.config['is_record'] = False
        self.send_config()
        self.schedule_state_labels[self.schedule_state["num"]]['text'] = "done"
        self.schedule_state["num"] += 1

    def end_schedule(self):
        self.console_dict['state'] = "idle"
        for work in self.schedule_event_lst:
            self.root.after_cancel(work)
        for child in self.stage_frame.winfo_children():
            child.configure(state='normal')
        for child in self.exp_frame.winfo_children():
            child.configure(state='normal')
        self.schedule_state["num"] = 0
        self.schedule_remove_but.configure(state="normal")
        self.schedule_go_but.configure(state="normal")
        self.schedule_stop_but.configure(state="disable")
        self.config['is_record'] = False
        self.send_config()
        self.start = 0

    def send_config(self):
        self.conn_send.send(self.config)

    def stage_butf_set(self):
        try:
            self.stage_setting()
        except ValueError as e:
            tk.messagebox.showerror(title="No send"
                                    , message="you type the wrong format, there must be int. "+e.__str__())
            return
        self.send_config()

    def stage_setting(self):
        for s, cam in enumerate(self.init_cams):
            self.config['cams'][s].update(show=self.stage_show_combos[s].current(), lag=float(self.stage_lag_entrys[s].get())
                                          , com=self.stage_com_vars[s].get(), threshold=int(self.stage_threshold_entrys[s].get())
                                          , center= self.stage_center_entrys[s].get(), vpath=self.stage_vpath_entrys[s].get()
                                          , sdir=self.stage_sdir_entrys[s].get())
        self.config["display"] = self.stage_display_var.get()
        self.config["light"] = self.stage_light_var.get()
        self.config['bk_color'] = int(self.stage_color_entry.get())

    def show_stage(self, load_config=None):
        if load_config is None:
            load_config = self.config
        is_disable = False
        for child in self.stage_frame.winfo_children():
            if child['state'] == tk.DISABLED:
                is_disable = True
            child.configure(state='normal')
        for s, cam in enumerate(self.init_cams):
            self.stage_show_combos[s].current(load_config['cams'][s]['show'])
            self.stage_lag_entrys[s].delete(0, tk.END)
            self.stage_lag_entrys[s].insert(tk.END, load_config['cams'][s]['lag'])
            self.stage_com_vars[s].set(load_config['cams'][s]['com'])
            self.stage_threshold_entrys[s].delete(0, tk.END)
            self.stage_threshold_entrys[s].insert(tk.END, load_config['cams'][s]['threshold'])
            self.stage_center_entrys[s].delete(0, tk.END)
            self.stage_center_entrys[s].insert(tk.END,  load_config['cams'][s].get("center", "center_err"))
            self.stage_vpath_entrys[s].delete(0, tk.END)
            self.stage_vpath_entrys[s].insert(tk.END, load_config['cams'][s].get('vpath', ""))
            self.stage_sdir_entrys[s].delete(0, tk.END)
            self.stage_sdir_entrys[s].insert(tk.END, load_config['cams'][s].get('sdir', ""))
        self.stage_display_var.set(self.config["display"])
        self.stage_light_var.set(self.config["light"])
        self.stage_color_entry.delete(0, tk.END)
        self.stage_color_entry.insert(tk.END, self.config.get('bk_color', 200))
        if is_disable:
            for child in self.stage_frame.winfo_children():
                child.configure(state='disable')

    def show_exp(self, load_config=None):
        if load_config is None:
            load_config = self.config
        self.exp_break_entry.insert(tk.END, load_config['break_sec'])
        self.exp_duration_entry.insert(tk.END, load_config['duration'])
        self.exp_filename_entry.insert(tk.END, load_config['folder'])

    def load_config(self, load_config: dict):
        for key, value in load_config.items():
            if key not in ["debug_cam", "is_running", "is_record", "record"]:
                self.config[key] = copy.deepcopy(value)

    def show_schedule(self):
        row_num = 2
        for label in self.schedule_label_lst:
            label.destroy()
        for label in self.schedule_state_labels:
            label.destroy()

        self.schedule_state_labels = []
        for num, sch_config in enumerate(self.schedule_config_lst):
            label = tk.Label(self.schedule_frame, text=num)
            label.grid(column=0, row=row_num)
            self.schedule_label_lst.append(label)
            label = tk.Label(self.schedule_frame, text=0)
            label.grid(column=1, row=row_num)
            self.schedule_label_lst.append(label)
            label = tk.Label(self.schedule_frame, text=sch_config['folder'])
            label.grid(column=2, row=row_num)
            self.schedule_label_lst.append(label)
            self.schedule_state_labels.append(tk.Label(self.schedule_frame, text="Not run"))
            self.schedule_state_labels[-1].grid(column=3, row=row_num)
            row_num += 1
        self.schedule_remove_comb['values'] = ["None"]+list(range(row_num-2))+["ALL"]
        self.schedule_remove_comb.grid(column=2, row=row_num, sticky="e")
        self.schedule_remove_but.grid(column=3, row=row_num, sticky="w")
        self.schedule_stop_but.grid(column=0, row=row_num)
        self.schedule_go_but.grid(column=4, row=row_num)
        self.schedule_save_but.grid(column=3, row=row_num+1)
        self.schedule_load_but.grid(column=2, row=row_num+1)

    def exp_setting(self):
        break_sec = int(self.exp_break_entry.get())
        duration_sec = int(self.exp_duration_entry.get())
        foldername = self.exp_filename_entry.get()
        self.config['folder'] = foldername
        self.config['duration'] = duration_sec
        self.config['break_sec'] = break_sec

    def exp_butf_add(self):
        try:
            self.stage_setting()
        except ValueError as e:
            tk.messagebox.showerror(title="NOT ADD"
                                    , message="you type the wrong format in stage, there must be int. "+e.__str__())
            return


        try:
            self.exp_setting()
        except ValueError as e:

            tk.messagebox.showerror(title="NOT ADD"
                                    , message="you type the wrong format in exp setting, there must be int. "+e.__str__())
            return

        self.schedule_config_lst.append(copy.deepcopy(self.config))
        self.show_schedule()

    def execute_config(self, config, accsec=0):
        duration_sec = config['duration']
        break_sec = config['break_sec']
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.load_config, config))
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.breaking))
        accsec += break_sec
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.load_config, config))
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.recording))
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.show_stage))
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.show_exp))
        accsec = duration_sec + 1 + accsec
        self.schedule_event_lst.append(self.root.after(accsec * 1000, self.end_exp))
        return accsec

    def schedule_butf_go(self):
        for child in self.stage_frame.winfo_children():
            child.configure(state='disable')
        for child in self.exp_frame.winfo_children():
            child.configure(state='disable')
        self.schedule_remove_but.configure(state="disable")
        self.schedule_go_but.configure(state="disable")
        self.schedule_stop_but.configure(state="normal")
        self.start = int(time.time())
        row_num = 2
        sec = 0
        self.schedule_event_lst = []
        for num, sch_config in enumerate(self.schedule_config_lst):
            sec = self.execute_config(sch_config, accsec=sec)
            label = tk.Label(self.schedule_frame, text=num)
            label.grid(column=0, row=row_num)
            self.schedule_label_lst.append(label)
            label = tk.Label(self.schedule_frame, text=datetime.timedelta(seconds=sec))
            label.grid(column=1, row=row_num)
            self.schedule_label_lst.append(label)
            label = tk.Label(self.schedule_frame, text=sch_config['folder'])
            label.grid(column=2, row=row_num)
            self.schedule_label_lst.append(label)
            self.schedule_state_labels[num]["text"] = "wait"
            self.schedule_state_labels[num].grid(column=3, row=row_num)
            row_num += 1
        self.schedule_event_lst.append(self.root.after(sec*1000, self.end_schedule))
        self.schedule_remove_comb['values'] = ["None"] + list(range(row_num - 2)) + ["ALL"]
        self.schedule_remove_comb.grid(column=2, row=row_num, sticky="e")
        self.schedule_remove_but.grid(column=3, row=row_num, sticky="w")
        self.schedule_stop_but.grid(column=0, row=row_num)
        self.schedule_go_but.grid(column=4, row=row_num)
        self.schedule_save_but.grid(column=3, row=row_num+1)
        self.schedule_load_but.grid(column=2, row=row_num+1)

    def schedule_butf_save(self):
        out_file = asksaveasfile(mode='w', defaultextension="txt")
        json.dump(self.schedule_config_lst, out_file, indent=4)
        out_file.close()

    def schedule_butf_load(self):
        open_file = askopenfilename()
        with open(open_file, 'r') as file:
            self.schedule_config_lst = json.load(file)
        self.show_schedule()

    def schedule_butf_stop(self):
        for event in self.schedule_event_lst:
            self.root.after_cancel(event)
        self.schedule_event_lst = []
        self.end_schedule()

    def schedule_butf_remove(self):
        num = self.schedule_remove_comb.current() - 1
        if num < 0:
            return
        if num == len(self.schedule_config_lst):
            self.schedule_config_lst = []
            self.show_schedule()
            return
        else:
            self.schedule_config_lst.pop(num)
            self.show_schedule()

    def exp_butf_dump(self):
        temp = copy.deepcopy(self.config.copy())
        duration_sec = int(self.exp_duration_entry.get())
        foldername = self.exp_filename_entry.get()
        temp['folder'] = foldername
        temp['duration'] = duration_sec
        for s, cam in enumerate(self.init_cams):
            temp['cams'][s] = CamStageConfig(show=self.stage_show_combos[s].current(), lag=int(self.stage_lag_entrys[s].get())
                                             , com=self.stage_com_vars[s].get(), threshold=int(self.stage_threshold_entrys[s].get())
                                             , center= self.stage_center_entrys[s].get(), vpath=self.stage_vpath_entrys[s].get()
                                             , sdir=self.stage_sdir_entrys[s].get(), model=self.stage_cam_labels[s]['text'])
        temp["display"] = self.stage_display_var.get()
        temp["light"] = self.stage_light_var.get()
        out_file = asksaveasfile(mode='w', defaultextension="txt")
        if out_file is None:
            return
        json.dump(temp, out_file, indent=4)
        out_file.close()

    def debug_combf_select(self, event):
        c_num = self.debug_camera_combo.current() - 1
        if c_num >= 0 and not self.config['cams'][c_num]["show"] == 1:
            c_num = -1
            return
        self.config["debug_cam"] = c_num
        cv2.namedWindow(self.init_cams[self.config['debug_cam']],)
        self.send_config()

    def update(self):
        if self.conn_recv.poll():
            mesg = self.conn_recv.recv()
            if 'img' in mesg:
                img = mesg['img']
                cv2.imshow(self.init_cams[self.config['debug_cam']], img[:, :, ::-1])
                cv2.waitKey(1)
                if self.config["debug_cam"] < 0:
                    self.send_config()
            elif self.config["debug_cam"] < 0:
                cv2.destroyAllWindows()
            if 'fps' in mesg:
                self.fps = mesg['fps']
            if 'center' in mesg:
                centers = mesg['center']
                for s, entry in enumerate(self.stage_center_entrys):
                    self.stage_center_entrys[s].delete(0, tk.END)
                    self.stage_center_entrys[s].insert(tk.END, centers[s].__str__())
            if 'vpath' in mesg:
                pathes = mesg['vpath']
                for s, path in enumerate(self.stage_vpath_entrys):
                    self.stage_vpath_entrys[s].delete(0, tk.END)
                    self.stage_vpath_entrys[s].insert(tk.END, pathes[s].__str__())
            if 'sdir' in mesg:
                pathes = mesg['sdir']
                for s, path in enumerate(self.stage_sdir_entrys):
                    self.stage_sdir_entrys[s].delete(0, tk.END)
                    self.stage_sdir_entrys[s].insert(tk.END, pathes[s].__str__())
        delta = 0
        if self.start:
            delta = int(time.time()) - self.start
        through = datetime.timedelta(seconds=delta)
        self.exp_current_label['text'] = self.console_dict['state'] + f", {through} pass ({self.fps:.2f})"
        self.root.after(10, self.update)


    def root_close(self):
        self.config["debug_cam"] = -1
        self.config["is_running"] = False
        self.send_config()
        time.sleep(1)
        while self.conn_recv.poll():
            _ = self.conn_recv.recv()
        self.root.destroy()


class Console(Process):
    def __init__(self, cams):
        super().__init__()
        self.conn1 = Pipe(False)
        self.conn2 = Pipe(False)
        self.cams = cams

    def run(self):
        self.window = ConfigWindow(self.conn1[0], self.conn2[1], self.cams)
        #self.show_console(self.conn1[0], self.conn2[1], self.cams)

    def poll(self):
        return self.conn2[0].poll()

    def getConfig(self) -> ConsoleConfig:
        return self.conn2[0].recv()

    def send(self, mes: dict):
        if self.conn1[1].closed:
            raise Exception()
        self.conn1[1].send(mes)
