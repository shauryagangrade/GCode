Output docs/demo.gif

Set Theme "Catppuccin Mocha"
Set FontSize 18
Set Width 1600
Set Height 900
Set Shell "bash"
Set TypingSpeed 155ms

Type "gcode --model nvidia/nemotron-3-super-120b-a12b:free --yes --session demo"
Enter

Sleep 3s

Type "Create a file named demo.py that prints 'Hello from GCode'."
Enter

# agent streams; write_file (+ maybe execute_bash) run automatically (--yes)
Sleep 55s

Type "Update it so it asks for the user's name before greeting them."
Enter

# edit_file streams — slowest turn
Sleep 55s

Type "Show me the file and check git status."
Enter

Sleep 45s

Ctrl+D

Sleep 6s
