from nicegui import ui

#local imports
from pages.mapPage import mapPage
from pages.loginPage import loginPage
import config

@ui.page('/')
def index():
    loginPage()

@ui.page('/mapPage')
def map():
    mapPage()

ui.run(storage_secret= config.Config.secret)
