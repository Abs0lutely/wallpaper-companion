"""Deferred page construction with stable tab indices and legacy widget access."""
from PySide6.QtWidgets import QWidget, QScrollArea

PAGE_ATTRIBUTES = {
    **dict.fromkeys((
        'provider_choice', 'provider_description', 'provider_fields_widget', 'provider_form',
        'provider_widgets', 'provider_cache', 'rendered_provider', 'tts_output',
        'filename_model', 'skip_existing_tts_audio', 'transferred_dialogues', 'transferred_lines',
        'start_api_button', 'check_api_button', 'reference_preview_button', 'lines',
        'generate_button', 'character_tools', 'character_choice', 'model_pair_choice',
        'scan_models_button', 'reference_choice', 'character_status', 'character_scan_timer',
        'character_scan_serial', 'character_scan_cache', 'active_character', 'tts_status',
        'tts_progress', 'tts_activity', 'tts_stage_output', 'generation_started_at',
        'pending_generation_total',
    ), 2),
    **dict.fromkeys((
        'run_mode', 'mode_notice', 'ui_language', 'language_notice',
        'we_dir', 'workshop_dir', 'monitor', 'poll_seconds',
        'backend_combos', 'operation_voice_enabled', 'operation_voice_dir', 'operation_voice_status',
        'startup_button', 'ffprobe_path', 'plugin_list', 'appearance_status',
        'auto_color', 'appearance_card',
    ), 3),
    **dict.fromkeys((
        'library_search', 'library_table', 'library_status', 'extra_library_roots',
        'library_tab_index',
    ), 4),
    **dict.fromkeys((
        'dialogue_context', 'dialogue_table', 'dialogue_category_choice', 'skip_existing_dialogue_audio',
        'rules_locale', 'dialogue_tab_index',
    ), 5),
    **dict.fromkeys((
        'audio_scope', 'audio_search', 'audio_table', 'audio_target',
        'audio_category', 'shared_audio_root', 'audio_library_status', 'audio_library_tab_index',
    ), 6),
}

class LazyPages:
    def page_pending(self, index):
        return index in self.__dict__.get("_page_builders", {})

    def __getattr__(self, name):
        index = PAGE_ATTRIBUTES.get(name)
        if index is not None and self.page_pending(index):
            self.ensure_page(index)
            if name in self.__dict__:
                return self.__dict__[name]
        raise AttributeError(name)

    def defer_page(self, index, title, builder):
        self._page_builders[index] = builder
        self.tabs.addTab(QWidget(), title)

    def ensure_page(self, index):
        builder = self._page_builders.pop(index, None)
        if builder is None:
            return
        previous = self.tabs.currentIndex()
        blocked = self.tabs.blockSignals(True)
        try:
            builder()
            content = self.tabs.widget(self.tabs.count()-1)
            self.tabs.removeTab(self.tabs.count()-1)
            old = self.tabs.widget(index)
            title = self.tabs.tabText(index)
            self.tabs.removeTab(index)
            old.deleteLater()
            scroll = content if index == 3 else QScrollArea()
            if index != 3:
                scroll.setWidgetResizable(True)
                scroll.setWidget(content)
            scroll.setMinimumSize(0, 0)
            self.tabs.insertTab(index, scroll, title)
            self.tabs.setCurrentIndex(previous)
            if index == 2:
                self.load_tts()
                self.tts_output.setText(self.voice_dir.text())
                if not self.page_pending(5):
                    self.skip_existing_tts_audio.setChecked(self.skip_existing_dialogue_audio.isChecked())
                self.skip_existing_tts_audio.toggled.connect(lambda checked: self.skip_existing_dialogue_audio.setChecked(checked) if not self.page_pending(5) else None)
            elif index == 3:
                self.build_appearance_settings()
                self.load_settings(apply_mode=False)
                self.apply_appearance()
            elif index == 4:
                self.library_tab_index = index
                self.render_library()
            elif index == 5:
                self.dialogue_tab_index = index
                if not self.page_pending(2):
                    self.skip_existing_dialogue_audio.setChecked(self.skip_existing_tts_audio.isChecked())
                self.render_dialogues()
            elif index == 6:
                self.audio_library_tab_index = index
            self.wrap_form_labels()
            from .help_ui import annotate_controls
            annotate_controls(self)
            if "autosave" in self.__dict__:
                keys = {2: "tts", 3: "runtime", 4: "roots", 6: "shared"}
                if index in keys:
                    self.autosave.remember(keys[index])
        finally:
            self.tabs.blockSignals(blocked)
        if index == 6 and previous == index:
            self.refresh_audio_library()

