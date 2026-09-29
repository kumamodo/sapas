from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

from sapas.core.utils import resolve_user_script


@dataclass
class EditorTabInfo:
    tab_id: str
    title: str
    path: Optional[Path]
    language: str
    buffer: str = ""
    original_disk_content: str = ""
    is_dirty: bool = False
    is_missing: bool = False


class MicroEditorScreen(ModalScreen[None]):
    """In-App Micro Editor for live script, flow, and configuration modifications."""

    BINDINGS = [
        Binding("escape", "close_editor", "Close", show=True),
        Binding("ctrl+s", "save_file", "Save", show=True),
        Binding("f1", "switch_tab_1", "Tab 1", show=False),
        Binding("f2", "switch_tab_2", "Tab 2", show=False),
        Binding("f3", "switch_tab_3", "Tab 3", show=False),
        Binding("f4", "switch_tab_4", "Tab 4", show=False),
        Binding("f5", "switch_tab_5", "Tab 5", show=False),
    ]

    def __init__(
        self,
        context=None,
        selected_step=None,
        test_steps=None,
        flow_path: Optional[Path] = None,
        session_snapshots: Optional[dict[Path, str]] = None,
        session_modified_files: Optional[set[Path]] = None,
        on_save_yaml: Optional[Callable[[], None]] = None,
        on_save_flow: Optional[Callable[[], Optional[str]]] = None,
    ) -> None:
        super().__init__()
        self.context = context
        self.selected_step = selected_step
        self.test_steps = test_steps or []
        self.flow_path = flow_path
        self.session_snapshots = session_snapshots if session_snapshots is not None else {}
        self.session_modified_files = session_modified_files if session_modified_files is not None else set()
        self.on_save_yaml = on_save_yaml
        self.on_save_flow = on_save_flow

        self.tabs: list[EditorTabInfo] = []
        self.active_tab_index = 0
        self.initial_cursor_line = 0
        self.is_flow_directive = False
        self._init_tabs()

    def _init_tabs(self) -> None:
        """Resolves target file paths and loads buffers for the 5 core tabs."""
        workspace_root = Path(self.context.get("WORKSPACE_ROOT", Path.cwd())) if self.context else Path.cwd()
        project_name = self.context.get("PROJECT_NAME", "") if self.context else ""
        station_name = self.context.get("STATION_NAME", "") if self.context else ""

        # Check if selected step is a Flow Control Directive (IF, END_IF, DELAY, PROMPT, CYCLE)
        self.is_flow_directive = False
        if self.selected_step:
            cmd = (self.selected_step.command or "").strip().lower()
            if cmd in ("if", "end_if", "delay", "prompt", "cycle") or getattr(self.selected_step, "is_condition", False):
                self.is_flow_directive = True

        # 1. Script (.py) Tab
        script_path = None
        if not self.is_flow_directive and self.selected_step and self.selected_step.flow_item:
            first_part = self.selected_step.flow_item.split()[0]
            try:
                script_path = resolve_user_script(first_part, project_name, workspace_root)
            except Exception:
                script_path = None

        # Fallback to first runnable step ONLY if not a flow directive and no script found
        if not self.is_flow_directive and not script_path and self.test_steps:
            for s in self.test_steps:
                cmd = (s.command or "").strip().lower()
                if cmd not in ("delay", "prompt", "if", "end_if", "cycle") and s.flow_item:
                    try:
                        script_path = resolve_user_script(s.flow_item.split()[0], project_name, workspace_root)
                        break
                    except Exception:
                        pass

        # 2. Flow (.flow) Tab
        flow_path = self.flow_path
        if not flow_path and project_name:
            cand = workspace_root / project_name / "flows" / f"{station_name}.flow"
            if cand.exists():
                flow_path = cand

        # 3. site_infra.yaml Tab
        site_infra_path = workspace_root / "site_infra.yaml"
        if not site_infra_path.exists():
            cand = workspace_root / "example" / "site_infra.yaml"
            if cand.exists():
                site_infra_path = cand

        # 4. station.yaml Tab
        station_path = None
        if project_name and station_name:
            cand = workspace_root / project_name / "stations" / station_name / "station.yaml"
            if cand.exists():
                station_path = cand

        # 5. project.yaml Tab
        project_path = None
        if project_name:
            cand = workspace_root / project_name / "configs" / "project.yaml"
            if cand.exists():
                project_path = cand

        script_title = script_path.name if script_path else ("(Flow Directive)" if self.is_flow_directive else "script.py")
        flow_title = flow_path.name if flow_path else "station.flow"
        site_infra_title = site_infra_path.name if site_infra_path else "site_infra.yaml"
        station_title = station_path.name if station_path else "station.yaml"
        project_title = project_path.name if project_path else "project.yaml"

        configs = [
            ("script", script_title, script_path, "python"),
            ("flow", flow_title, flow_path, "python"),
            ("site_infra", site_infra_title, site_infra_path, "yaml"),
            ("station", station_title, station_path, "yaml"),
            ("project", project_title, project_path, "yaml"),
        ]

        self.tabs = []
        for tid, title, path, lang in configs:
            content = ""
            missing = False
            if tid == "script" and self.is_flow_directive:
                step_name = self.selected_step.item_label.strip() if self.selected_step else "Flow Directive"
                content = (
                    "# ==========================================================================\n"
                    f"# [NOTICE] Selected item '{step_name}' is a Flow Control Directive.\n"
                    "# Flow directives (IF, END_IF, DELAY, PROMPT) do not have a Python script.\n"
                    "# They are defined directly inside the active .flow file.\n"
                    "#\n"
                    f"# -> Sapas has automatically opened [F2] {flow_title} for direct editing.\n"
                    "# ==========================================================================\n"
                )
            elif path and path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                except Exception as e:
                    content = f"# Error reading file {path}:\n# {e}"
            else:
                missing = True
                content = f"# Target file not found:\n# {path if path else '(Undefined)'}\n"

            tab = EditorTabInfo(
                tab_id=tid,
                title=title,
                path=path,
                language=lang,
                buffer=content,
                original_disk_content=content if not missing and not (tid == "script" and self.is_flow_directive) else "",
                is_dirty=False,
                is_missing=missing if not (tid == "script" and self.is_flow_directive) else False,
            )
            self.tabs.append(tab)

        # Smart tab selection: If flow directive, open Tab 1 (Flow) by default and locate target line
        if self.is_flow_directive:
            self.active_tab_index = 1
            flow_content = self.tabs[1].buffer
            flow_lines = flow_content.splitlines()
            cond_target = (self.selected_step.condition or self.selected_step.flow_item or "").strip()
            cmd_target = (self.selected_step.command or "").strip().lower()

            for line_no, raw_line in enumerate(flow_lines):
                line_str = raw_line.strip()
                if line_str.startswith("#"):
                    continue
                if cmd_target == "if" and ("if " in line_str.lower() or "if\t" in line_str.lower()):
                    if cond_target and cond_target in line_str:
                        self.initial_cursor_line = line_no
                        break
                    elif not cond_target:
                        self.initial_cursor_line = line_no
                        break
                elif cmd_target == "end_if" and line_str.lower().startswith("end_if"):
                    self.initial_cursor_line = line_no
                    break
                elif cmd_target in ("delay", "prompt") and line_str.lower().startswith(cmd_target):
                    if cond_target and cond_target in line_str:
                        self.initial_cursor_line = line_no
                        break
                    else:
                        self.initial_cursor_line = line_no
                        break

    @staticmethod
    def _build_footer_guide() -> Text:
        t = Text()
        t.append("[F1~F5] ", style="bold yellow")
        t.append("Switch Tab   │   ", style="bold white")
        t.append("[Ctrl+S] ", style="bold green")
        t.append("Save & Backup   │   ", style="bold white")
        t.append("[Esc] ", style="bold cyan")
        t.append("Close Editor", style="bold white")
        return t

    def compose(self) -> ComposeResult:
        step_label = f"Step: [{self.selected_step.item_id}] {self.selected_step.item_label}" if self.selected_step else "General Diagnosis"
        active_tab = self.tabs[self.active_tab_index]

        yield Container(
            Horizontal(
                Static("🛠️ SAPAS IN-APP MICRO EDITOR", id="editor-title"),
                Static(step_label, id="editor-step-label"),
                id="editor-header",
            ),
            Horizontal(
                Button(self._get_tab_label(0), id="editor-tab-0", classes=f"editor-tab-btn{' active' if self.active_tab_index == 0 else ''}"),
                Button(self._get_tab_label(1), id="editor-tab-1", classes=f"editor-tab-btn{' active' if self.active_tab_index == 1 else ''}"),
                Button(self._get_tab_label(2), id="editor-tab-2", classes=f"editor-tab-btn{' active' if self.active_tab_index == 2 else ''}"),
                Button(self._get_tab_label(3), id="editor-tab-3", classes=f"editor-tab-btn{' active' if self.active_tab_index == 3 else ''}"),
                Button(self._get_tab_label(4), id="editor-tab-4", classes=f"editor-tab-btn{' active' if self.active_tab_index == 4 else ''}"),
                id="editor-tab-bar",
            ),
            Horizontal(
                Static("", id="editor-file-path"),
                Static("", id="editor-file-status"),
                id="editor-meta-bar",
            ),
            TextArea(
                active_tab.buffer,
                language=active_tab.language,
                theme="monokai",
                show_line_numbers=True,
                id="editor-text-area",
            ),
            Horizontal(
                Static(self._build_footer_guide(), id="editor-hotkey-guide"),
                Static("", id="editor-feedback-status"),
                id="editor-footer",
            ),
            id="editor-dialog",
        )

    def on_mount(self) -> None:
        self._update_tab_buttons()
        self._update_meta_bar()
        text_area = self.query_one("#editor-text-area", TextArea)
        if self.initial_cursor_line > 0:
            text_area.move_cursor((self.initial_cursor_line, 0), center=True)
        text_area.focus()

    def _get_tab_label(self, index: int) -> str:
        tab = self.tabs[index]
        star = " *" if tab.is_dirty else "  "
        return f"{tab.title}{star}"

    def _update_tab_buttons(self) -> None:
        for idx in range(len(self.tabs)):
            try:
                btn = self.query_one(f"#editor-tab-{idx}", Button)
                new_label = self._get_tab_label(idx)
                if str(btn.label) != new_label:
                    btn.label = new_label
                if idx == self.active_tab_index:
                    btn.add_class("active")
                else:
                    btn.remove_class("active")
            except Exception:
                pass

    def _update_meta_bar(self) -> None:
        tab = self.tabs[self.active_tab_index]
        path_label = self.query_one("#editor-file-path", Static)
        status_label = self.query_one("#editor-file-status", Static)

        if tab.tab_id == "script" and self.is_flow_directive:
            path_label.update("📁 Path: (Flow Directive - Defined in Flow file)")
            status_label.update("● FLOW DIRECTIVE")
            status_label.styles.color = "yellow"
        elif tab.is_missing:
            path_str = f"📁 Path: {tab.path} (NOT FOUND)" if tab.path else "📁 Path: (Not Configured)"
            path_label.update(path_str)
            status_label.update("● MISSING")
            status_label.styles.color = "red"
        else:
            path_label.update(f"📁 Path: {tab.path}")
            if tab.is_dirty:
                status_label.update("● MODIFIED (Unsaved)")
                status_label.styles.color = "yellow"
            else:
                status_label.update("CLEAN")
                status_label.styles.color = "green"

    def _switch_tab(self, new_index: int) -> None:
        if new_index == self.active_tab_index or not (0 <= new_index < len(self.tabs)):
            return

        text_area = self.query_one("#editor-text-area", TextArea)
        # Store current editor content in active tab buffer
        current_tab = self.tabs[self.active_tab_index]
        current_tab.buffer = text_area.text
        if not current_tab.is_missing and current_tab.buffer != current_tab.original_disk_content:
            current_tab.is_dirty = True

        # Switch to new tab
        self.active_tab_index = new_index
        next_tab = self.tabs[new_index]

        text_area.text = next_tab.buffer
        text_area.language = next_tab.language
        self._update_tab_buttons()
        self._update_meta_bar()
        self.query_one("#editor-feedback-status", Static).update("")
        text_area.focus()

    def action_switch_tab_1(self) -> None:
        self._switch_tab(0)

    def action_switch_tab_2(self) -> None:
        self._switch_tab(1)

    def action_switch_tab_3(self) -> None:
        self._switch_tab(2)

    def action_switch_tab_4(self) -> None:
        self._switch_tab(3)

    def action_switch_tab_5(self) -> None:
        self._switch_tab(4)

    @on(Button.Pressed, ".editor-tab-btn")
    def on_tab_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id and btn_id.startswith("editor-tab-"):
            idx = int(btn_id.split("-")[-1])
            self._switch_tab(idx)

    @on(TextArea.Changed, "#editor-text-area")
    def on_editor_text_changed(self) -> None:
        tab = self.tabs[self.active_tab_index]
        text_area = self.query_one("#editor-text-area", TextArea)
        tab.buffer = text_area.text
        if not tab.is_missing:
            dirty = tab.buffer != tab.original_disk_content
            if dirty != tab.is_dirty:
                tab.is_dirty = dirty
                self._update_tab_buttons()
                self._update_meta_bar()

    def action_save_file(self) -> None:
        """Saves current buffer to disk, takes snapshot if first edit, and triggers YAML reload."""
        tab = self.tabs[self.active_tab_index]
        feedback = self.query_one("#editor-feedback-status", Static)

        if tab.tab_id == "script" and self.is_flow_directive:
            flow_name = self.tabs[1].title if len(self.tabs) > 1 else "Flow"
            feedback.update(f"Notice: Flow directives have no standalone script. Edit [F2] {flow_name} instead.")
            feedback.styles.color = "yellow"
            return

        if not tab.path:
            feedback.update("Cannot save: No valid file path configured.")
            feedback.styles.color = "red"
            return

        text_area = self.query_one("#editor-text-area", TextArea)
        tab.buffer = text_area.text

        # Record in-memory baseline snapshot for session rollback before first save
        if tab.path not in self.session_snapshots:
            if tab.path.exists():
                try:
                    self.session_snapshots[tab.path] = tab.path.read_text(encoding="utf-8")
                except Exception:
                    self.session_snapshots[tab.path] = tab.original_disk_content
            else:
                self.session_snapshots[tab.path] = ""

        # Write new content to disk
        try:
            tab.path.parent.mkdir(parents=True, exist_ok=True)
            tab.path.write_text(tab.buffer, encoding="utf-8")
            tab.original_disk_content = tab.buffer
            tab.is_dirty = False
            tab.is_missing = False
            self.session_modified_files.add(tab.path)

            self._update_tab_buttons()
            self._update_meta_bar()

            # Hot-reload if a YAML config or Flow file was modified
            is_yaml = tab.path.suffix.lower() in (".yaml", ".yml")
            is_flow = tab.path.suffix.lower() == ".flow"
            if is_yaml and self.on_save_yaml:
                self.on_save_yaml()
                feedback.update("✓ Saved & YAML hot-reloaded into context!")
                feedback.styles.color = "green"
            elif is_flow and self.on_save_flow:
                err = self.on_save_flow()
                if err:
                    feedback.update(f"Saved, but flow syntax warning: {err}")
                    feedback.styles.color = "yellow"
                else:
                    if hasattr(self.app, "test_steps"):
                        self.test_steps = getattr(self.app, "test_steps", self.test_steps)
                    feedback.update("✓ Saved & Flow steps hot-reloaded into table!")
                    feedback.styles.color = "green"
            else:
                feedback.update(f"✓ Saved '{tab.path.name}' successfully!")
                feedback.styles.color = "green"

        except Exception as e:
            feedback.update(f"Save failed: {e}")
            feedback.styles.color = "red"

    def action_close_editor(self) -> None:
        """Exits Micro Editor modal. Prompts confirmation if any tab has unsaved modifications."""
        text_area = self.query_one("#editor-text-area", TextArea)
        current_tab = self.tabs[self.active_tab_index]
        current_tab.buffer = text_area.text
        if not current_tab.is_missing and current_tab.buffer != current_tab.original_disk_content:
            current_tab.is_dirty = True

        dirty_tabs = [t for t in self.tabs if t.is_dirty]
        if not dirty_tabs:
            self.dismiss()
            return

        self.app.push_screen(
            UnsavedChangesScreen(dirty_tabs=dirty_tabs),
            callback=self._handle_unsaved_decision,
        )

    def _handle_unsaved_decision(self, decision: str | None) -> None:
        if decision == "save":
            for tab in self.tabs:
                if tab.is_dirty and tab.path:
                    # Record baseline snapshot before save
                    if tab.path not in self.session_snapshots:
                        if tab.path.exists():
                            try:
                                self.session_snapshots[tab.path] = tab.path.read_text(encoding="utf-8")
                            except Exception:
                                self.session_snapshots[tab.path] = tab.original_disk_content
                        else:
                            self.session_snapshots[tab.path] = ""

                    try:
                        tab.path.parent.mkdir(parents=True, exist_ok=True)
                        tab.path.write_text(tab.buffer, encoding="utf-8")
                        tab.original_disk_content = tab.buffer
                        tab.is_dirty = False
                        self.session_modified_files.add(tab.path)
                    except Exception:
                        pass

            if any(t.path and t.path.suffix.lower() in (".yaml", ".yml") for t in self.tabs) and self.on_save_yaml:
                self.on_save_yaml()
            if any(t.path and t.path.suffix.lower() == ".flow" for t in self.tabs) and self.on_save_flow:
                self.on_save_flow()
            self.dismiss()
        elif decision == "discard":
            for tab in self.tabs:
                tab.buffer = tab.original_disk_content
                tab.is_dirty = False
            self.dismiss()
        else:
            # "cancel" or None
            try:
                self.query_one("#editor-text-area", TextArea).focus()
            except Exception:
                pass


class UnsavedChangesScreen(ModalScreen[str]):
    """Confirmation modal when closing Micro Editor with unsaved changes."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("s", "save", "Save & Close", show=True),
        Binding("d", "discard", "Discard & Close", show=True),
    ]

    def __init__(self, dirty_tabs: list[EditorTabInfo]) -> None:
        super().__init__()
        self.dirty_tabs = dirty_tabs

    def compose(self) -> ComposeResult:
        files_bullet = "\n".join(f"• {t.title}" for t in self.dirty_tabs)
        msg_text = (
            "The following file(s) have unsaved modifications:\n\n"
            f"{files_bullet}\n\n"
            "Do you want to save changes before closing?"
        )
        yield Container(
            Static("⚠️  UNSAVED CHANGES", id="unsaved-dialog-title"),
            Static(msg_text, id="unsaved-dialog-message"),
            Horizontal(
                Button("Save & Close (s)", variant="success", id="btn-unsaved-save"),
                Button("Discard & Close (d)", variant="error", id="btn-unsaved-discard"),
                Button("Keep Editing (Esc)", id="btn-unsaved-cancel"),
                id="unsaved-dialog-actions",
            ),
            id="unsaved-dialog-container",
        )

    def action_save(self) -> None:
        self.dismiss("save")

    def action_discard(self) -> None:
        self.dismiss("discard")

    def action_cancel(self) -> None:
        self.dismiss("cancel")

    @on(Button.Pressed, "#btn-unsaved-save")
    def on_save_clicked(self) -> None:
        self.dismiss("save")

    @on(Button.Pressed, "#btn-unsaved-discard")
    def on_discard_clicked(self) -> None:
        self.dismiss("discard")

    @on(Button.Pressed, "#btn-unsaved-cancel")
    def on_cancel_clicked(self) -> None:
        self.dismiss("cancel")
