import re

with open('c:/Projeler/katib/ui/control_center.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('class SettingsDialog(QDialog):', 'class ControlCenterWindow(QDialog):')

with open('c:/Projeler/katib/ui/control_center.py', 'w', encoding='utf-8') as f:
    f.write(code)
