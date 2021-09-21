import sublime
import sublime_plugin


class PinTabCommand(sublime_plugin.WindowCommand):
    def run(self, group, index):
        view = self.window.views_in_group(group)[index]
        settings = view.settings()
        if settings.get('pinned_tab', False):
            settings.set('pinned_tab', False)
            print('unpinned file:', view.file_name())
        else:
            settings.set('pinned_tab', True)
            print('pinned file:', view.file_name())

    def description(self, group, index):
        view = self.window.views_in_group(group)[index]
        if view.settings().get('pinned_tab', False):
            return 'Unpin This Tab'
        else:
            return 'Pin This Tab'


class PinTabListener(sublime_plugin.EventListener):
    def on_window_command(self, window, command, args):
        # print("on_window_command", command, args)
        if command in {'close', 'close_transient'}:
            if window.active_view().settings().get('pinned_tab', False):
                opt = sublime.yes_no_cancel_dialog(
                    'You are trying to close a pinned tab',
                    yes_title='Switch to next',
                    no_title='Close it')
                if opt == sublime.DIALOG_CANCEL:
                    return ('*cancel*', {})
                if opt == sublime.DIALOG_YES:
                    # 'next_view_in_stack'
                    return ('next_view', {})
                return None
