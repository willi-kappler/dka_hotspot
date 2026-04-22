from nicegui import ui

def germanyMap():
    m = ui.leaflet(center=(48.6616, 9.3501), zoom=8).classes('w-full').style('height: 80vh')
    #m = ui.leaflet(center=(51.1657, 10.4515), zoom=6).classes('w-full').style('height: 80vh') #vh= screen/viewport height
    #
    #  .style = regular css
    ui.label().bind_text_from(m, 'zoom', lambda zoom: f'Zoom: {zoom}')
    with ui.grid(columns=2):
        ui.button(icon='zoom_in', on_click=lambda: m.set_zoom(m.zoom + 1))
        ui.button(icon='zoom_out', on_click=lambda: m.set_zoom(m.zoom - 1))