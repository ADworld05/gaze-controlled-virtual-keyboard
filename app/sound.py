from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect, QMediaPlayer, QAudioOutput
from .settings import ROOT


class Feedback:
    def __init__(self, parent, settings):
        self.s = settings
        self.effects = {}
        for name in ('select', 'navigate'):
            path = ROOT / f'assets/sounds/{name}.wav'
            effect = QSoundEffect(parent)
            if path.exists():
                effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setLoopCount(1)
            self.effects[name] = effect
        self.voice = QMediaPlayer(parent)
        self.output = QAudioOutput(parent)
        self.voice.setAudioOutput(self.output)

    def play(self, name, key=None):
        if not self.s.sound:
            return
        if name == 'navigate' and not self.s.navigation_sound:
            return
        for effect in self.effects.values():
            effect.stop()
        self.voice.stop()  # No speech queue or overlap.
        effect = self.effects[name]
        effect.setVolume(self.s.volume)
        effect.play()
        if name == 'select' and self.s.speech and key:
            filename = {'Space': 'space', 'Backspace': 'backspace'}.get(key, key.lower())
            if not (filename.isalnum() and len(filename) <= 9):
                return
            path = ROOT / f'assets/sounds/voice/{filename}.mp3'
            if path.exists():
                effect.stop()
                self.output.setVolume(self.s.volume)
                self.voice.setSource(QUrl.fromLocalFile(str(path)))
                self.voice.play()

    def stop(self):
        for effect in self.effects.values():
            effect.stop()
        self.voice.stop()
