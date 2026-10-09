# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A desktop task list for Linux and macOS, started with the `todo-qt` command.
- Tasks have a title, a start and end time, and a done checkbox. New tasks are
  pre-filled to start at the next full hour and last 30 minutes, and they're
  added at the bottom of the list.
- Edit a task's title and times from the inline form. Press Enter in the title
  field to confirm.
- Drag a task to reorder the list. The moved task and every task below it are
  rescheduled back to back, keeping their durations.
- A day start time (09:00 by default). Changing it reschedules the whole list
  from that time.
- Done tasks are struck through. Unfinished tasks whose end time has passed are
  highlighted as overdue, and the highlight updates on its own within a minute.
- Delete a task with the Delete button or the Delete key (Backspace on macOS),
  and clear all completed tasks at once. Undo (Ctrl+Z, or Cmd+Z on macOS)
  restores the last delete or clear.
- Every change is saved automatically to `tasks.json` in your user data folder
  (`~/.local/share/todo-qt` on Linux, `~/Library/Application Support/todo-qt` on
  macOS), readable only by you. Set `TODO_QT_DATA_DIR` to use another folder.
- If the saved file can't be read, the app starts with an empty list and tells
  you why. The unreadable file is kept as `tasks.<date-time>.corrupt` and is
  never overwritten. If a save fails, the app says so and keeps your change in
  the list.
