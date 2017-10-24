#!/usr/bin/python

"""
Configuration module for sln2cmake.
It is better not to edit this file directly, but copy is as sln2cmake_config_user.py and edit then
sln2cmake will try to load sln2cmake_config_user.py if it exists, then fallback to sln2cmake_config.py
"""

# private
SETUP_AFTER_HEAD_SECTION = ''

class Setup:

    # The pipeline: [project_serach] -> [loader] -> [project] -> [cmake_generate]
    # During [loader] operation, before [project] is filled, 
    # You may store data in loader.user_load_data field (then copied to project.user_load_data by loader)

    # --- [project search] customization ---

    # public
    # returns list of ignored projects files names (w/o extension)
    @staticmethod
    def get_ignored_projects():
        IGNORED_PROJECTS = [ ] # default is empty
        return IGNORED_PROJECTS

    # --- [loader] customization ---

    # protected
    @staticmethod
    def get_loader_user_load_data(loader):
        return loader.user_load_data

    # public [event]
    # just after loader init (init user_load_data here)
    @staticmethod
    def on_load_init(loader):
        pass # default is nothing to do

    # public [event]
    # after import section parsed
    @staticmethod
    def on_load_import_file_list(loader, import_filename_list):
        user_load_data = Setup.get_loader_user_load_data(loader)
        pass # default is nothing to do

    # public [event]
    # after project is loaded and project info is filled
    @staticmethod
    def on_load_done(loader, project):
        pass # default is nothing to do

    # --- [project] customization ---

    # protected
    @staticmethod
    def get_project_user_load_data(project):
        return project.user_load_data

    # public
    # adjust project options after load by project-specific manner
    @staticmethod
    def proc_project_custom_params(project):
        user_load_data = Setup.get_project_user_load_data(project)
        pass # default is nothing to do

    # --- [cmake_generate] customization ---

    # public
    # root cmake file: section after head
    @staticmethod
    def cmake_root_get_after_head_section():
        return SETUP_AFTER_HEAD_SECTION # default = empty string

    # public [event]
    # before output to cmake file is done
    @staticmethod
    def cmake_generate_begin(cmake_file,project):
        pass # default is nothing to do

    # public [event]
    # after output to cmake file is done
    @staticmethod
    def cmake_generate_end(cmake_file,project):
        user_load_data = Setup.get_project_user_load_data(project)
        pass # default is nothing to do

