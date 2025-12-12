#!/usr/bin/env python3
import sys
import argparse
import time
import glob
import os

try:
    import numpy as np
except ImportError:
    print("Error: numpy is required for this script.")
    sys.exit(1)

try:
    import tkinter as tk
    from PIL import Image, ImageTk
except ImportError:
    tk = None

class YUVImage:
    def __init__(self, y_data, u_data, v_data, width, height):
        self.y_data = y_data
        self.u_data = u_data
        self.v_data = v_data
        self.width = width
        self.height = height

def read_header_value(f):
    token = b""
    while True:
        char = f.read(1)
        if not char:
            return None if not token else token
        
        if chr(char[0]).isspace():
            if token: return token
        elif char == b'#':
            while True:
                c = f.read(1)
                if c == b'\n' or not c: break
        else:
            token += char

def read_pgm_yuv(filename):
    with open(filename, 'rb') as f:
        t1 = read_header_value(f)
        if t1 != b'P5':
            raise ValueError("Not a valid PGM P5 file")
        
        t2 = read_header_value(f)
        t3 = read_header_value(f)
        t4 = read_header_value(f)
        
        pgm_w = int(t2)
        pgm_h = int(t3)
        
        data = f.read()

    video_width = pgm_w
    video_height = int(pgm_h / 1.5)
    
    y_size = video_width * video_height
    y_data = np.frombuffer(data, dtype=np.uint8, count=y_size, offset=0)
    
    rest_data = data[y_size:]
    
    chroma_h = video_height // 2
    chroma_w = video_width // 2
    
    uv_data = np.frombuffer(rest_data, dtype=np.uint8, count=chroma_h * chroma_w * 2)
    
    uv_matrix = uv_data.reshape((chroma_h, 2 * chroma_w))
    
    u_data = uv_matrix[:, :chroma_w].flatten()
    v_data = uv_matrix[:, chroma_w:].flatten()
    
    return YUVImage(y_data, u_data, v_data, video_width, video_height)

def yuv420_to_rgb(y_data, u_data, v_data, width, height):
    Y = y_data.reshape((height, width)).astype(np.float32)
    
    chroma_h = height // 2
    chroma_w = width // 2
    
    U_small = u_data.reshape((chroma_h, chroma_w)).astype(np.float32)
    V_small = v_data.reshape((chroma_h, chroma_w)).astype(np.float32)
    
    U = U_small.repeat(2, axis=0).repeat(2, axis=1)
    V = V_small.repeat(2, axis=0).repeat(2, axis=1)
    
    c = Y - 16
    d = U - 128
    e = V - 128
    
    c = Y
    
    R = c + 1.402 * e
    G = c - 0.344136 * d - 0.714136 * e
    B = c + 1.772 * d
    
    R = np.clip(R, 0, 255).astype(np.uint8)
    G = np.clip(G, 0, 255).astype(np.uint8)
    B = np.clip(B, 0, 255).astype(np.uint8)
    
    rgb = np.dstack((R, G, B))
    return rgb

def write_ppm(filename, rgb_data):
    height, width, _ = rgb_data.shape
    header = f"P6\n{width} {height}\n255\n"
    print(f"Writing {filename}...")
    with open(filename, 'wb') as f:
        f.write(header.encode('ascii'))
        f.write(rgb_data.tobytes())

def bob_deinterlace(y_data, u_data, v_data, width, height):
    Y = y_data.reshape((height, width))
    Y_top = Y[0::2, :]
    Y_bot = Y[1::2, :]
    
    Y1 = Y_top.repeat(2, axis=0) 
    Y2 = Y_bot.repeat(2, axis=0) 
    
    chroma_h = height // 2
    chroma_w = width // 2
    
    U = u_data.reshape((chroma_h, chroma_w))
    V = v_data.reshape((chroma_h, chroma_w))
    
    U_top = U[0::2, :]
    V_top = V[0::2, :]
    U_bot = U[1::2, :]
    V_bot = V[1::2, :]
    
    U1 = U_top.repeat(2, axis=0)
    V1 = V_top.repeat(2, axis=0)
    U2 = U_bot.repeat(2, axis=0)
    V2 = V_bot.repeat(2, axis=0)
    
    rgb1 = yuv420_to_rgb(Y1.flatten(), U1.flatten(), V1.flatten(), width, height)
    rgb2 = yuv420_to_rgb(Y2.flatten(), U2.flatten(), V2.flatten(), width, height)
    
    return rgb1, rgb2

def adaptive_deinterlace(y_curr, u_curr, v_curr, y_prev, u_prev, v_prev, width, height, threshold, block_size):
    Y = y_curr.reshape((height, width))
    Y_prev = y_prev.reshape((height, width))
    
    Y_top_curr = Y[0::2, :]
    Y_top_prev = Y_prev[0::2, :]
    
    Y_bot_curr = Y[1::2, :]
    Y_bot_prev = Y_prev[1::2, :]
    
    h_field = height // 2
    
    def get_motion_mask(f1, f2, h, w, bs):
        ny = h // bs
        nx = w // bs
        
        cy = ny * bs
        cx = nx * bs
        
        c1 = f1[:cy, :cx].astype(np.int32)
        c2 = f2[:cy, :cx].astype(np.int32)
        
        blocks_diff = np.abs(c1 - c2)
        blocks = blocks_diff.reshape(ny, bs, nx, bs).transpose(0, 2, 1, 3)
        
        sad = blocks.sum(axis=(2, 3)) 
        
        mask_grid = sad > threshold
        
        mask_pixel = mask_grid.repeat(bs, axis=0).repeat(bs, axis=1)
        
        full_mask = np.zeros((h, w), dtype=bool)
        full_mask[:cy, :cx] = mask_pixel
        return full_mask

    mask_top = get_motion_mask(Y_top_curr, Y_top_prev, h_field, width, block_size)
    mask_bot = get_motion_mask(Y_bot_curr, Y_bot_prev, h_field, width, block_size)
    
    def process_plane(curr, h, w, m_top, m_bot):
        P = curr.reshape((h, w))
        P_top = P[0::2, :]
        P_bot = P[1::2, :]
        
        Bob_1 = P_top.repeat(2, axis=0) 
        Bob_2 = P_bot.repeat(2, axis=0) 
        
        Weave = P
        
        M1 = m_top.repeat(2, axis=0) 
        M2 = m_bot.repeat(2, axis=0)
        
        Out1 = np.where(M1, Bob_1, Weave)
        Out2 = np.where(M2, Bob_2, Weave)
        
        return Out1.flatten(), Out2.flatten()
        
    y1, y2 = process_plane(Y, height, width, mask_top, mask_bot)
    
    cw = width // 2
    ch = height // 2
    
    cm_top = mask_top[::2, ::2]
    cm_bot = mask_bot[::2, ::2]
    
    u1, u2 = process_plane(u_curr.reshape(ch, cw), ch, cw, cm_top, cm_bot)
    v1, v2 = process_plane(v_curr.reshape(ch, cw), ch, cw, cm_top, cm_bot)
    
    rgb1 = yuv420_to_rgb(y1, u1, v1, width, height)
    rgb2 = yuv420_to_rgb(y2, u2, v2, width, height)
    
    return rgb1, rgb2


class VideoPlayer:
    def __init__(self, files, fps, deinterlace=None, threshold=3000, block_size=16):
        self.files = files
        self.fps = fps
        self.deinterlace = deinterlace
        self.threshold = threshold
        self.block_size = block_size
        
        if self.deinterlace in ['bob', 'adaptive']:
            self.fps *= 2
            
        self.delay = int(1000 / self.fps)
        self.idx = 0
        self.sub_idx = 0 
        
        self.prev_img = None 
        
        self.root = tk.Tk()
        self.root.title("YUV Player")
        
        self.label = tk.Label(self.root)
        self.label.pack()
        
        self.root.after(0, self.update_frame)
        self.root.mainloop()
        
    def update_frame(self):
        start_time = time.time()
        
        if self.idx >= len(self.files):
            self.idx = 0
            self.prev_img = None
            
        fname = self.files[self.idx]
        try:
            img_yuv = read_pgm_yuv(fname)
            
            if self.deinterlace == 'bob':
                rgb1, rgb2 = bob_deinterlace(img_yuv.y_data, img_yuv.u_data, img_yuv.v_data, 
                                             img_yuv.width, img_yuv.height)
                rgb = rgb1 if self.sub_idx == 0 else rgb2
                if self.sub_idx == 0:
                    self.sub_idx = 1
                else:
                    self.sub_idx = 0
                    self.idx += 1
            
            elif self.deinterlace == 'adaptive':
                if self.prev_img is None:
                    rgb1, rgb2 = bob_deinterlace(img_yuv.y_data, img_yuv.u_data, img_yuv.v_data, 
                                                 img_yuv.width, img_yuv.height)
                else:
                    rgb1, rgb2 = adaptive_deinterlace(
                        img_yuv.y_data, img_yuv.u_data, img_yuv.v_data,
                        self.prev_img.y_data, self.prev_img.u_data, self.prev_img.v_data,
                        img_yuv.width, img_yuv.height,
                        self.threshold, self.block_size
                    )
                
                rgb = rgb1 if self.sub_idx == 0 else rgb2
                
                if self.sub_idx == 1:
                    self.prev_img = img_yuv 
                    self.sub_idx = 0
                    self.idx += 1
                else:
                    self.sub_idx = 1
                    
            else:
                rgb = yuv420_to_rgb(img_yuv.y_data, img_yuv.u_data, img_yuv.v_data, 
                                    img_yuv.width, img_yuv.height)
                self.idx += 1
                self.prev_img = img_yuv
            
            im = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=im)
            
            self.label.config(image=imgtk)
            self.label.image = imgtk
            title_extra = ""
            if self.deinterlace:
                title_extra = f" ({self.deinterlace} Field {self.sub_idx+1})"
            self.root.title(f"YUV Player - {fname}{title_extra}")
            
        except Exception as e:
            print(f"Error decoding {fname}: {e}")
            self.idx += 1
            self.sub_idx = 0
        
        elapsed = (time.time() - start_time) * 1000
        wait = max(1, int(self.delay - elapsed))
        
        self.root.after(wait, self.update_frame)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert/Play mpeg2dec PGM YUV files")
    parser.add_argument("inputs", nargs='+', help="Input PGM files")
    parser.add_argument("--output", help="Output PPM file (only if single input)")
    parser.add_argument("--display", action="store_true", help="Display to screen")
    parser.add_argument("--fps", type=float, default=25.0, help="Framerate for playback")
    parser.add_argument("--deinterlace", choices=['bob', 'adaptive'], help="Deinterlacing mode")
    parser.add_argument("--threshold", type=int, default=3000, help="Threshold for adaptive deinterlace (SAD per block)")
    parser.add_argument("--block-size", type=int, default=16, help="Block size for adaptive deinterlace")
    
    args = parser.parse_args()
    
    files = []
    for i in args.inputs:
        files.extend(glob.glob(i) if '*' in i else [i])
    files = sorted(files)
    
    if not files:
        print("No input files found")
        sys.exit(1)
        
    if args.display:
        if tk is None:
            print("Error: tkinter or PIL not installed/working")
            sys.exit(1)
        player = VideoPlayer(files, args.fps, args.deinterlace, args.threshold, args.block_size)
    else:
        if args.output:
            if len(files) > 1:
                print("Warning: Multiple inputs but single output file specified. Converting only first one.")
            img = read_pgm_yuv(files[0])
            if args.deinterlace == 'bob':
                print("Bob deinterlacing for single file output: saving 2 files.")
                f1, f2 = bob_deinterlace(img.y_data, img.u_data, img.v_data, img.width, img.height)
                base, ext = os.path.splitext(args.output)
                write_ppm(f"{base}_1{ext}", f1)
                write_ppm(f"{base}_2{ext}", f2)
            else:
                rgb = yuv420_to_rgb(img.y_data, img.u_data, img.v_data, img.width, img.height)
                write_ppm(args.output, rgb)
        else:
            print("No output file specified and --display not used.")
