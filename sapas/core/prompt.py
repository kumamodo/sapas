import sys
from pathlib import Path

# Try to import tkinter and PIL
try:
    import tkinter as tk
    from PIL import Image, ImageTk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


def show_operator_prompt(image_path: Path | None = None, text_content: str | None = None, logger=None) -> None:
    """
    Displays a centered, topmost, dark-themed operator prompt window.
    If GUI is not available (e.g., headless terminal), falls back to terminal prompt.
    """
    # Helper log functions
    def log_info(msg):
        if logger:
            logger.info(msg)
        else:
            print(f"[INFO] {msg}")

    def log_warn(msg):
        if logger:
            logger.warning(msg)
        else:
            print(f"[WARNING] {msg}")

    # Fallback message formatting
    fallback_text = text_content or ""
    if image_path:
        img_name = image_path.name
        fallback_text = f"{fallback_text} (Image: {img_name})" if fallback_text else f"(Image: {img_name})"

    # If GUI is not available, run headless fallback
    if not TK_AVAILABLE:
        log_warn("GUI libraries (tkinter or Pillow) are not available. Falling back to terminal prompt.")
        log_info(f"[PROMPT] {fallback_text}")
        input("Press [Enter] to continue...")
        return

    try:
        root = tk.Tk()
        root.title("Sapas Operator Prompt")
        
        # Configure topmost
        root.attributes("-topmost", True)
        
        # sapas-classic Theme Colors
        BG_COLOR = "#071016"       # Deep dark slate/blue
        FG_COLOR = "#d9e1e7"       # Light slate grey/white
        ACCENT_COLOR = "#f2c94c"   # Warm gold/yellow
        PANEL_BG = "#0B1C28"       # Dark blue-grey panel
        BORDER_COLOR = "#0E4C70"   # Muted ocean blue border
        BTN_BG = "#0E4C70"         # Ocean blue
        BTN_FG = "#d9e1e7"
        BTN_ACTIVE_BG = "#f2c94c"
        BTN_ACTIVE_FG = "#071016"
        ERR_COLOR = "#ff5d5d"      # Soft red

        # Enable borderless custom window decoration
        root.overrideredirect(True)
        root.configure(bg=BG_COLOR, highlightthickness=2, highlightbackground=BORDER_COLOR)

        # 1. Custom Title Bar Frame
        title_bar = tk.Frame(root, bg=PANEL_BG, height=35)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False) # Keep height fixed
        
        # Title text label
        title_label = tk.Label(
            title_bar, 
            text=" ⚙️ Sapas Operator Prompt", 
            fg=ACCENT_COLOR, 
            bg=PANEL_BG, 
            font=("Segoe UI", 10, "bold")
        )
        title_label.pack(side=tk.LEFT, padx=10)
        
        # Custom Close Button (✕) on the right
        close_btn = tk.Button(
            title_bar,
            text="✕ ",
            bg=PANEL_BG,
            fg=FG_COLOR,
            activebackground="#ff5d5d",
            activeforeground="#ffffff",
            bd=0,
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            command=root.destroy,
            cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 5))
        
        # Hover effect for close button
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#ff5d5d", fg="#ffffff"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=PANEL_BG, fg=FG_COLOR))
        
        # Drag window functionality
        def start_move(event):
            root._drag_start_x = event.x
            root._drag_start_y = event.y

        def on_move(event):
            x = root.winfo_x() + (event.x - root._drag_start_x)
            y = root.winfo_y() + (event.y - root._drag_start_y)
            root.geometry(f"+{x}+{y}")

        title_bar.bind("<ButtonPress-1>", start_move)
        title_bar.bind("<B1-Motion>", on_move)
        title_label.bind("<ButtonPress-1>", start_move)
        title_label.bind("<B1-Motion>", on_move)

        # Main container frame
        main_frame = tk.Frame(root, bg=BG_COLOR, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Image section
        img_label = None
        photo_img = None
        image_err_msg = None

        if image_path:
            if image_path.exists():
                try:
                    # Open using Pillow
                    pil_img = Image.open(image_path)
                    # Limit maximum size to fit typical screens comfortably
                    pil_img.thumbnail((800, 600))
                    photo_img = ImageTk.PhotoImage(pil_img)
                    
                    img_label = tk.Label(main_frame, image=photo_img, bg=BG_COLOR)
                    img_label.pack(pady=(0, 15))
                except Exception as e:
                    image_err_msg = f"Failed to load image: {e}"
            else:
                image_err_msg = f"Prompt picture missing: {image_path.name}"

        # If there was an error loading the image, display a clean error label
        if image_err_msg:
            log_warn(image_err_msg)
            err_label = tk.Label(
                main_frame,
                text=f"⚠️ [{image_err_msg}]",
                fg=ERR_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 12, "bold"),
                wraplength=600
            )
            err_label.pack(pady=(0, 15))

        # 2. Text instruction section
        if text_content:
            text_label = tk.Label(
                main_frame,
                text=text_content,
                fg=FG_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 13),
                wraplength=700,
                justify=tk.LEFT
            )
            text_label.pack(pady=(0, 20))
        elif not image_path:
            # If neither text nor image is specified, show a default prompt
            text_label = tk.Label(
                main_frame,
                text="Please perform manual action and confirm to proceed.",
                fg=ACCENT_COLOR,
                bg=BG_COLOR,
                font=("Segoe UI", 13, "bold"),
                wraplength=700
            )
            text_label.pack(pady=(0, 20))

        # 3. Confirmation Button
        def confirm():
            root.destroy()

        # Custom-styled confirmation button
        btn = tk.Button(
            main_frame,
            text="OK / Confirm",
            command=confirm,
            width=18,
            height=2,
            font=("Segoe UI", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=BTN_ACTIVE_BG,
            activeforeground=BTN_ACTIVE_FG,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2"
        )
        btn.pack(pady=(10, 0))
        btn.focus_set()

        # Hover effects for button
        def on_enter(e):
            btn.config(bg=BTN_ACTIVE_BG, fg=BTN_ACTIVE_FG)
            
        def on_leave(e):
            btn.config(bg=BTN_BG, fg=BTN_FG)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        # Bind Keyboard Events (Enter / Space)
        root.bind("<Return>", lambda e: confirm())
        root.bind("<space>", lambda e: confirm())

        # Center Window calculation
        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        
        # Add a minimum width for purely text dialogs
        if w < 400:
            w = 400
            
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

        # Force window focus and button focus
        root.lift()
        root.focus_force()
        btn.focus_force()

        # Add a slight delay to ensure Windows OS finishes rendering and processes the focus request
        root.after(100, lambda: root.focus_force())
        root.after(150, lambda: btn.focus_force())

        # Block and run Tkinter loop
        root.mainloop()

    except Exception as e:
        log_warn(f"Tkinter window creation failed: {e}. Falling back to terminal prompt.")
        log_info(f"[PROMPT] {fallback_text}")
        input("Press [Enter] to continue...")
