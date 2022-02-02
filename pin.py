from os.path import basename as _basename
import time

import sublime
import sublime_plugin


class PinTabCommand(sublime_plugin.WindowCommand):
    def run(self, group, index):
        view = sublime.active_window().views_in_group(group)[index]
        settings = view.settings()
        if settings.get('pinned_tab', False):
            settings.set('pinned_tab', False)
            print('PinTab: unpinned file:', view.file_name())
        else:
            settings.set('pinned_tab', True)
            print('PinTab: pinned file:', view.file_name())

    def description(self, group, index):
        view = sublime.active_window().views_in_group(group)[index]
        if view.settings().get('pinned_tab', False):
            return 'Unpin This Tab'
        else:
            return 'Pin This Tab'


class TabsGuardListener(sublime_plugin.EventListener):
    def access(self, view):
        view.settings().set('tab_access_time', _strtime())

    def get_access_time(self, view : sublime.View):
        return view.settings().setdefault('tab_access_time', _strtime())

    def on_activated(self, view):
        self.access(view)

    def on_load(self, view):
        settings = sublime.load_settings('PinTab.sublime-settings')
        tabs_limit = settings.get('tabs_limit', 15)
        tabs_limit = max(tabs_limit, 8)
        self.access(view)
        self.select_view_to_close(sublime.active_window(), tabs_limit, view)

    def on_new(self, view):
        self.on_load(view)

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

    def select_view_to_close(self,
            window : sublime.Window,
            tabs_limit : int,
            curr_view : sublime.View):

        def on_select(index):
            if index != -1:
                view = closable_views[index]
                view.close()
                self.select_view_to_close(window, tabs_limit, curr_view)
            else:
                window.focus_view(curr_view)

        def on_highlight(index):
            if index != 1:
                view = closable_views[index]
                window.focus_view(view)

        def closable(view : sublime.View) -> bool:
            return not (view.is_dirty()  or _is_pinned(view))

        def make_item(filename, tstr):
            return sublime.QuickPanelItem(
                _basename(filename),
                details=[_relpath(window.folders(), filename)],
                annotation=f'last access at: {tstr}',
            )

        views = window.views()
        if len(views) <= tabs_limit:
            window.focus_view(curr_view)
            return
        view_access_times = sorted(
            [(v, self.get_access_time(v)) for v in filter(closable, views)],
            key=lambda p: p[1]
        )
        closable_views = [view for view, _ in view_access_times]
        items = [
            make_item(view.file_name() or 'Untitled', tstr)
            for view, tstr in view_access_times
        ]
        window.show_quick_panel(
            items,
            on_select=on_select,
            on_highlight=on_highlight,
            placeholder="Tabs are too crowded, select one file to close")


def _strtime():
    return time.strftime("%m/%d %H:%M:%S")

def _is_pinned(view):
    return view.settings().get('pinned_tab', False)

def _relpath(roots, path):
    for folder in roots:
        if path.startswith(folder):
            return f'{_basename(folder)}{path[len(folder):]}'
    return path
