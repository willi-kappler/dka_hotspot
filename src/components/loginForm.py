from nicegui import app, ui


#just sample user ids. change later
USERS = {
    "willi": {"password": "1234", "role": "maintainer"},
    "kobe":   {"password": "5678", "role": "user"}
}

class LoginForm: #willi AEM app
    def __init__(self): # class constructor
        with ui.dialog() as error_dialog: #popup error .dialog = popup
            with ui.card(): #like div HTML
                ui.label("Login failed!").classes("text-2xl text-red-500 font-bold")
        
        self.error_dialog = error_dialog

    def checkLogin(self): #modify later
        user = USERS.get(self.username.value)
        if user and user["password"] == self.password.value: #user exists and pass match
            app.storage.user["username"] = self.username.value
            app.storage.user["role"] = user["role"]
            ui.navigate.to("/mapPage")
        else:
            self.error_dialog.open()

    def show(self): #willi AEM app
        with ui.card().classes("absolute-center items-center w-96 p-20"):
            ui.label("Map App").classes("text-2xl font-bold")
            ui.label("Please log in:").classes("text-xl")
            self.username = ui.input(label="Username")
            self.password = ui.input(label="Password", password=True) # pass True hide characters
            ui.button("Login", icon="login", on_click=self.checkLogin).classes("rounded-lg")
            # icons fonts.google.com/icons
            #normal-case