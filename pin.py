from os.path import basename as _basename
import time
from typing import List

import sublime
import sublime_plugin


KEY_VIEW_IS_TRANSIENT = 'pintab.view_is_transient'
KEY_VIEW_ACCESS_TIME = 'pintab.view_access_time'
KEY_VIEW_IS_PINNED = 'pintab.view_is_pinned'


class settings:
    on_change_key = 'pintab.reload_settings'
    name = 'PinTab.sublime-settings'
    obj : sublime.Settings
    tabs_limit = 15
    auto_close_oldest_tab = False
    check_when_new_view = True

    @classmethod
    def read(cls):
        cls.tabs_limit = max(cls.obj.get('tabs_limit', 15), 8)
        cls.auto_close_oldest_tab = cls.obj.get('auto_close_oldest_tab', False)
        cls.check_when_new_view = cls.obj.get('check_when_new_view', True)

    @classmethod
    def load(cls):
        cls.obj = sublime.load_settings(cls.name)
        cls.obj.add_on_change(cls.on_change_key, cls.read)
        cls.read()

    @classmethod
    def clear(cls):
        cls.obj.clear_on_change(cls.on_change_key)


def plugin_loaded():
    sublime.set_timeout_async(settings.load)

def plugin_unloaded():
    settings.clear()


def get_access_time_of_view(view : sublime.View) -> str:
    return view.settings().setdefault(KEY_VIEW_ACCESS_TIME, _strtime())


def update_access_time_of_view(view : sublime.View) -> None:
    view.settings().set(KEY_VIEW_ACCESS_TIME, _strtime())


def sort_closable_views_with_access_time(views : List[sublime.View]):
    def closable(view : sublime.View) -> bool:
        return not (view.is_dirty()  or _is_pinned_view(view))

    return sorted(
        [(v, get_access_time_of_view(v)) for v in filter(closable, views)],
        key=lambda p: p[1]
    )


class OnDoneTask(object):
    def __init__(self, task):
        self.__task = task
        self.__need_run = False

    def set(self):
        self.__need_run = True

    def run(self):
        if self.__need_run:
            self.__task()


def select_view_to_close(
    window : sublime.Window,
    views : List[sublime.View],
    task : OnDoneTask) -> None:
    def on_select(index):
        if index != -1:
            view = closable_views[index]
            view.close()
            check_window_views_number(window, task)
        else:
            task.run()

    def on_highlight(index):
        if index != 1:
            view = closable_views[index]
            window.focus_view(view)

    def make_item(filename, tstr):
        return sublime.QuickPanelItem(
            _basename(filename),
            details=[_relpath(window.folders(), filename)],
            annotation=f'last access at: {tstr}',
        )

    views_with_access_time = sort_closable_views_with_access_time(views)
    closable_views = [view for view, _ in views_with_access_time]
    items = [
        make_item(view.file_name() or 'Untitled', tstr)
        for view, tstr in views_with_access_time
    ]
    state = f'{len(views)} > {settings.tabs_limit}'
    window.run_command('hide_overlay')
    window.show_quick_panel(
        items,
        on_select=on_select,
        on_highlight=on_highlight,
        placeholder=f"Tabs are too crowded ({state}), select one to close")


def check_window_views_number(window : sublime.Window, task : OnDoneTask):
    views = window.views(include_transient=False)
    if len(views) <= settings.tabs_limit:
        task.run()
        return
    if settings.auto_close_oldest_tab:
        window.run_command('close_tabs_to_limit')
    else:
        task.set()
        select_view_to_close(window, views, task)


def access_view_and_check_views_number(view : sublime.View) -> None:
    if settings.tabs_limit == 0:
        return
    def run():
        update_access_time_of_view(view)
        window = sublime.active_window()
        ondone = OnDoneTask(lambda: window.focus_view(view))
        check_window_views_number(window, ondone)

    sublime.set_timeout(run)


class TabsGuardListener(sublime_plugin.EventListener):
    def on_window_command(self, window, command, args):
        # print("on_window_command", command, args)
        if command in {'close', 'close_transient'}:
            if window.active_view().settings().get(KEY_VIEW_IS_PINNED, False):
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

    def on_new(self, view):
        if settings.check_when_new_view:
            access_view_and_check_views_number(view)

    def on_load(self, view):
        if _is_normal_view(view):
            if view.sheet().is_transient():
                view.settings().set(KEY_VIEW_IS_TRANSIENT, True)
            else:
                access_view_and_check_views_number(view)

    def on_activated(self, view : sublime.View):
        if _is_normal_view(view):
            if view.settings().get(KEY_VIEW_IS_TRANSIENT):
                view.settings().erase(KEY_VIEW_IS_TRANSIENT)
                access_view_and_check_views_number(view)
            else:
                update_access_time_of_view(view)


class CloseTabsToLimitCommand(sublime_plugin.WindowCommand):
    def run(self, *args, **kwargs):
        views = self.window.views()
        if len(views) <= settings.tabs_limit:
            return
        for view, _ in sort_closable_views_with_access_time(views
            )[:len(views) - settings.tabs_limit]:
            view.close()

    def is_visible(self) -> bool:
        return len(self.window.views()) > settings.tabs_limit

    def description(self, *args, **kwargs) -> str:
        return f'Close Tabs to Limit ({settings.tabs_limit})'


class PinTabCommand(sublime_plugin.WindowCommand):
    def run(self, group, index):
        view = sublime.active_window().views_in_group(group)[index]
        settings = view.settings()
        if settings.get(KEY_VIEW_IS_PINNED, False):
            settings.set(KEY_VIEW_IS_PINNED, False)
            print('PinTab: unpinned file:', view.file_name())
        else:
            settings.set(KEY_VIEW_IS_PINNED, True)
            print('PinTab: pinned file:', view.file_name())

    def description(self, group, index):
        view = sublime.active_window().views_in_group(group)[index]
        if view.settings().get(KEY_VIEW_IS_PINNED, False):
            return 'Unpin This Tab'
        else:
            return 'Pin This Tab'


def _strtime():
    return time.strftime("%m/%d %H:%M:%S")

def _is_pinned_view(view):
    return view.settings().get(KEY_VIEW_IS_PINNED, False)

def _is_normal_view(view : sublime.View):
    return view.element() is None

def _relpath(roots, path):
    for folder in roots:
        if path.startswith(folder):
            return f'{_basename(folder)}{path[len(folder):]}'
    return path
