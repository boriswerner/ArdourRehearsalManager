#! /usr/bin/env python3
import PySimpleGUI as sg
import pandas as pd
import os
import random
import subprocess
import select
import socket

import json

from pythonosc import udp_client
from pythonosc import osc_server
import mido
import mido.backends.rtmidi

from threading import Thread

DEBUG_ACTIVE = True
CONFIG_FILE = "config.cfg"
headings = ['Active', 'Playlist Number', 'Song', 'Duration', 'BPM', 'Key', 'Mood', 'Kit #', 'Kitname', 'Ardour File']
osc_client = None
stop_threads = False
songfolder = os.path.dirname(os.path.abspath(__file__))

def debug_print(message):
    if DEBUG_ACTIVE:
        print(message)

def get_midi_output_devices():
    return mido.get_output_names()

def send_midi_program_change(device_name, midi_channel, program_number):
    try:
        with mido.open_output(device_name) as midi_port:
            program_change_message = mido.Message('program_change', program=program_number, channel=midi_channel-1)
            
            midi_port.send(program_change_message)
            debug_print(f"Sent MIDI Program Change {program_number} to MIDI Channel {midi_channel} on {device_name}")
    except Exception as e:
        sg.popup_error(f"Error sending MIDI Program Change message:\n{e}")

def midi_dialog():
    midi_output_devices = get_midi_output_devices()

    layout = [
        [sg.Text("MIDI Device:"), sg.DropDown(midi_output_devices, key='-MIDI_DEVICE-', default_value=midi_output_devices[0])],
        [sg.Text("MIDI Channel:"), sg.Input(key='-MIDICHANNEL-', default_text='10')],
        [sg.Text("Program Number:"), sg.Input(key='-PROGRAM_NUMBER-', default_text='1')],
        [sg.Button("Send MIDI Program Change Message", key='-SEND_MIDI_PC-')],
    ]

    dialog = sg.Window("Send MIDI PC", layout, modal=True)

    while True:
        event, values = dialog.read()

        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        elif event == '-SEND_MIDI_PC-':
            device_name = values['-MIDI_DEVICE-']
            midi_channel = int(values['-MIDICHANNEL-'])
            program_number = int(values['-PROGRAM_NUMBER-'])
            send_midi_program_change(device_name, midi_channel, program_number)

    dialog.close()

    return None

def osc_dialog(osc_server_address,osc_server_port):
    layout = [
        [sg.Text("OSC Server Address:"), sg.Input(key='-OSCADDR-', default_text=osc_server_address)],
        [sg.Text("OSC Server Port:"), sg.Input(key='-OSCPORT-', default_text=osc_server_port), sg.Button('Connect to OSC Server', key='-CONNECTOSC-'), sg.Button('Start OSC Server', key='-STARTOSC-')],
        [sg.Text("OSC Message to Send:"), sg.Input(key='-OSCMSG-', default_text="/set_surface/strip_types")],
        [sg.Text("OSC Message Payload:"), sg.Input(key='-OSCMSGPAYLOAD-', default_text="159"), sg.Button('Send OSC Message', key='-SENDOSCMSG-')],        
        [sg.Button('Send OSC Test Message', key='-SENDOSCTESTMSG-')],   
     ]
    global osc_client
    dialog = sg.Window("OSC Connection", layout, modal=True)

    while True:
        event, values = dialog.read()
        global osc_thread
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        elif event == '-CONNECTOSC-':
            # Handle file path input change
            osc_server_address = values['-OSCADDR-']
            osc_server_port = values['-OSCPORT-']
            debug_print(f"Selected osc_server_address: {osc_server_address}")
            debug_print(f"Selected osc_server_port: {osc_server_port}")
            save_config(None, None, osc_server_address, osc_server_port, None)
            # Handle OSC connection
            osc_server_address = values['-OSCADDR-']
            osc_server_port = values['-OSCPORT-']
            if osc_server_address and osc_server_port:
                osc_client = connect_to_osc_server(osc_server_address, int(osc_server_port))
            
        elif event == '-STARTOSC-':
            # Start OSC server in a separate thread
            osc_server_port = 8000
            if osc_thread:
                osc_thread.join()  # Wait for the previous OSC thread to finish
            osc_thread = start_osc_server_in_thread(osc_server_port)
        elif event == '-SENDOSCMSG-':
            # Send OSC message
            if osc_client:
                osc_message = values['-OSCMSG-']
                osc_payload = values['-OSCMSGPAYLOAD-']
                debug_print(f"Sending OSC message: {osc_message} {osc_payload}")
                osc_client.send_message(osc_message, float(osc_payload))  # You can modify the second argument based on your needs
        elif event == '-SENDOSCTESTMSG-':
            songname = "My Song"
            duration = 240  # in seconds
            bpm = 120.5
            key = 3
            mood = "Happy"
            chords_structure = "C G Am F"
            lyrics = "La la la..."

            # Send OSC messages with the example data
            send_osc_messages(songname, duration, bpm, key, mood, chords_structure, lyrics)
                    
    dialog.close()

    return None
def send_osc_messages(songname, duration, bpm, key, mood, next_songname):
    if osc_client:
        minutes, seconds = map(int, duration.split(':'))
        total_seconds = minutes * 60 + seconds
        print(total_seconds)
        # Send individual OSC messages for each piece of information
        osc_client.send_message("/songname", songname)
        osc_client.send_message("/duration", total_seconds)
        osc_client.send_message("/bpm", bpm)
        osc_client.send_message("/key", key)
        osc_client.send_message("/mood", mood)
        osc_client.send_message("/chordsstructure", read_chords_structure(songname))
        osc_client.send_message("/lyrics", read_lyrics(songname))
        osc_client.send_message("/nextsongname", next_songname)

def read_chords_structure(songname):
    filename = os.path.join(songfolder, songname, "structure.txt")
    print(f"read_chords_structure: {filename}")
    try:
        with open(filename, 'r') as file:
            content = file.read()
            return content
    except FileNotFoundError:
        print(f"Error: File not found at {filename}")
        return ""
    except Exception as e:
        print(f"Error: {e}")
        return ""

def read_lyrics(songname):
    filename = os.path.join(songfolder, songname, "lyrics.txt")
    print(f"read_lyrics: {filename}")
    try:
        with open(filename, 'r') as file:
            content = file.read()
            return content
    except FileNotFoundError:
        print(f"Error: File not found at {filename}")
        return ""
    except Exception as e:
        print(f"Error: {e}")
        return ""


def edit_entry(selected_index, window):
    
    table_data = window['-TABLE-'].get()
    selected_row = table_data[selected_index]
    layout = [
        [sg.Text('Edit Entry')],
        [sg.Text('Active:'), sg.Checkbox('', default=selected_row[0], key='-ACTIVE-')],
        [sg.Text('Playlist Number:'), sg.Input(key='-PLAYLIST_NUMBER-', default_text=selected_row[1], disabled=True, size=(5, 1)), sg.Button('Get Playlist Number')],
        [sg.Text('Patchname:'), sg.Input(key='-PATCHNAME-', default_text=selected_row[2])],
        [sg.Text('Duration:'), sg.Input(key='-DURATION-', default_text=selected_row[3])],
        [sg.Text('BPM:'), sg.Input(key='-BPM-', default_text=selected_row[4])],
        [sg.Text('Key:'), sg.Input(key='-KEY-', default_text=selected_row[5])],        
        [sg.Text('Mood:'), sg.DropDown(['N/A', 'Aggressiv / Wütend', 'Ausgeglichen / Relaxed', 'Clever / Neugierig', 'Cool / Lässig', 'Elegant', 'Energiegeladen / Kraftvoll', 'Episch / Monumental', 'Fröhlich / Heiter', 'Futuristisch', 'Hoffnungsvoll / Romantisch', 'Lustig / Albern', 'Motiviert / Optimistisch', 'Spannend / Gefährlich', 'Traurig / Nostalgisch'], key='-MOOD-', default_value=selected_row[6])],
        [sg.Text('Kit Number:'), sg.Input(key='-KIT_NUMBER-', default_text=selected_row[7])],
        [sg.Text('Kitname:'), sg.Input(key='-KITNAME-', default_text=selected_row[8])],
        [sg.Text('Ardour File:'), sg.Input(key='-ARDOUR_FILE-', default_text=selected_row[9])],
        [sg.Button('Save'), sg.Button('Save & Next'), sg.Button('Save & Previous'), sg.Button('Delete Row'), sg.Button('Cancel')],
    ]


    edit_window = sg.Window('Edit Entry', layout, modal=True)

    while True:
        event, values = edit_window.read()

        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        elif event == 'Get Playlist Number':
            # Get the next available playlist number
            playlist_number = get_next_playlist_number(table_data)
            values['-PLAYLIST_NUMBER-'] = playlist_number
            edit_window['-PLAYLIST_NUMBER-'].update(value=playlist_number)
        elif event == 'Save':
            
            table_data[selected_index][0] = values['-ACTIVE-']
            table_data[selected_index][1] = values['-PLAYLIST_NUMBER-']
            table_data[selected_index][2] = values['-PATCHNAME-']
            table_data[selected_index][3] = values['-DURATION-']
            table_data[selected_index][4] = values['-BPM-']
            table_data[selected_index][5] = values['-KEY-']
            table_data[selected_index][6] = values['-MOOD-']
            table_data[selected_index][7] = values['-KIT_NUMBER-']
            table_data[selected_index][8] = values['-KITNAME-']
            table_data[selected_index][9] = values['-ARDOUR_FILE-']
            # Implement your own validation logic for the time format
            if ":" in table_data[selected_index][3] and table_data[selected_index][3].count(":") == 1:
                minutes, seconds = map(int, table_data[selected_index][3].split(":"))
                total_seconds = minutes * 60 + seconds
            else:
                print("Invalid time format. Please use MM:SS")
            
            window['-TABLE-'].update(values=table_data)
            update_setlist_json(table_data)
            break
        elif event == 'Save & Next':
            table_data[selected_index][0] = values['-ACTIVE-']
            table_data[selected_index][1] = values['-PLAYLIST_NUMBER-']
            table_data[selected_index][2] = values['-PATCHNAME-']
            table_data[selected_index][3] = values['-DURATION-']
            table_data[selected_index][4] = values['-BPM-']
            table_data[selected_index][5] = values['-KEY-']
            table_data[selected_index][6] = values['-MOOD-']
            table_data[selected_index][7] = values['-KIT_NUMBER-']
            table_data[selected_index][8] = values['-KITNAME-']
            table_data[selected_index][9] = values['-ARDOUR_FILE-']
            # Implement your own validation logic for the time format
            if ":" in table_data[selected_index][3] and table_data[selected_index][3].count(":") == 1:
                minutes, seconds = map(int, table_data[selected_index][3].split(":"))
                total_seconds = minutes * 60 + seconds
            else:
                print("Invalid time format. Please use MM:SS")
            
            window['-TABLE-'].update(values=table_data)
            update_setlist_json(table_data)
            selected_index = (selected_index + 1) % len(table_data)
            edit_window.close()
            edit_entry(selected_index, window)
        elif event == 'Save & Previous':
            table_data[selected_index][0] = values['-ACTIVE-']
            table_data[selected_index][1] = values['-PLAYLIST_NUMBER-']
            table_data[selected_index][2] = values['-PATCHNAME-']
            table_data[selected_index][3] = values['-DURATION-']
            table_data[selected_index][4] = values['-BPM-']
            table_data[selected_index][5] = values['-KEY-']
            table_data[selected_index][6] = values['-MOOD-']
            table_data[selected_index][7] = values['-KIT_NUMBER-']
            table_data[selected_index][8] = values['-KITNAME-']
            table_data[selected_index][9] = values['-ARDOUR_FILE-']
            # Implement your own validation logic for the time format
            if ":" in table_data[selected_index][3] and table_data[selected_index][3].count(":") == 1:
                minutes, seconds = map(int, table_data[selected_index][3].split(":"))
                total_seconds = minutes * 60 + seconds
            else:
                print("Invalid time format. Please use MM:SS")
            
            window['-TABLE-'].update(values=table_data)
            update_setlist_json(table_data)
            selected_index = (selected_index - 1) % len(table_data)
            edit_window.close()
            edit_entry(selected_index, window)
        elif event == 'Delete Row':
            delete_rows(window, [selected_index])
            edit_window.close()
            break
    edit_window.close()

def get_next_playlist_number(table_data):
    # Get the next available playlist number
    playlist_numbers = set(entry[1] for entry in table_data if entry[1])
    all_numbers = set(range(1, len(table_data) + 1))
    available_numbers = all_numbers - playlist_numbers
    return min(available_numbers) if available_numbers else ''

def delete_rows(window, selected_indices):
    if not selected_indices:
        return

    table_data = window['-TABLE-'].get()
    remaining_rows = [row for index, row in enumerate(table_data) if index not in selected_indices]

    # Update the table and rewrite the setlist JSON file
    window['-TABLE-'].update(values=remaining_rows)
    #highlight_all_rows(window)
    update_setlist_json(remaining_rows)

def add_entry(window):
    table_data = window['-TABLE-'].get()
    new_entry = [True, '', '', '00:00', '120', 'N/A', '', '', '']
    table_data.append(new_entry)
    window['-TABLE-'].update(values=table_data)
    #highlight_all_rows(window)
    edit_entry(len(table_data) - 1, window)

def move_up(window, selected_index):
    if not selected_index:
        return

    table_data = window['-TABLE-'].get()
    if selected_index > 0:
        table_data[selected_index], table_data[selected_index - 1] = table_data[selected_index - 1], table_data[selected_index]
        window['-TABLE-'].update(values=table_data)
        window['-TABLE-'].Widget.selection_set(selected_index)
        window['-TABLE-'].Widget.see(selected_index)
        update_setlist_json(table_data)

def move_down(window, selected_index):
    if not selected_index:
        return

    table_data = window['-TABLE-'].get()
    if selected_index < len(table_data) - 1:
        table_data[selected_index], table_data[selected_index + 1] = table_data[selected_index + 1], table_data[selected_index]
        window['-TABLE-'].update(values=table_data)
        window['-TABLE-'].Widget.selection_set(selected_index + 2)
        window['-TABLE-'].Widget.see(selected_index + 2)
        update_setlist_json(table_data)
   
def update_setlist_json(data):
    output_path = os.path.join(os.getcwd(), 'spdsx_output.json')

    json_data = []
    playlist_counter = 1

    for entry in data:
        active = entry[0]
        playlist_number = entry[1] if active else ''
        patchname = entry[2]
        duration = entry[3]
        bpm = entry[4]
        key = entry[5]
        mood = entry[6]
        kitnumber = entry[7]
        kitname = entry[8]
        ardourfile = entry[9]

        json_entry = {
            'Active': active,
            'Playlist Number': playlist_number,
            'Song': patchname,
            'Duration': duration,
            'BPM': bpm,
            'KEY': key,
            'Mood': mood,
            'Kit #': kitnumber,
            'Kitname': kitname,
            'Ardour File': ardourfile
        }

        json_data.append(json_entry)

        if active:
            playlist_counter += 1

    with open(output_path, 'w') as json_file:
        json.dump(json_data, json_file, indent=2)


def highlight_all_rows(window):
    # Highlight all rows in the table
    table_rows = len(window['-TABLE-'].get())
    if table_rows > 0:
        window['-TABLE-'].Widget.selection_set(list(range(1, table_rows + 1)))

def read_json_and_display(file_path, window):
    debug_print(f"Reading JSON file: {file_path}")
    # Read JSON file into a DataFrame
    try:
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
            df = pd.DataFrame(data)
    except Exception as e:
        sg.popup_error(f"Error reading JSON file:\n{e}")
        return
    debug_print(df.values.tolist())
    # Update the table with new data
    vals = df.values.tolist()
    window['-TABLE-'].update(values=vals, num_rows=min(25, len(df)))
    #highlight_all_rows(window)

# def shuffle_rows(window, selected_values):
#     # Shuffle the rows in the table keeping only the selected songs
#     current_values = window['-TABLE-'].get()
#     if current_values:
#         selected_songs = [row for index, row in enumerate(current_values) if index in selected_values]
#         random.shuffle(selected_songs)
#         window['-TABLE-'].update(values=selected_songs)
#         highlight_all_rows(window)


def shuffle_rows(window, selected_values):
    # Shuffle the rows in the table keeping only the selected songs
    current_values = window['-TABLE-'].get()
    if current_values:
        selected_songs = [row for index, row in enumerate(current_values) if index in selected_values]
        active_songs = [row for row in selected_songs if row[0]]

        # Shuffle only the active songs
        random.shuffle(active_songs)
        # Update the table with the shuffled songs
        shuffled_songs = []
        not_selected_songs = []
        song_index = 0

        for index, row in enumerate(current_values):
            if row[0] and row in active_songs:
                # If the row is active and in active_songs, assign the index in active_songs
                shuffled_songs.append(row[:1] + [active_songs.index(row) + 1] + row[2:])
            else:
                # If the row is not active or not in active_songs, assign an empty string to row[1]
                not_selected_songs.append(row[:1] + [''] + row[2:])
        shuffled_songs.sort(key=lambda x: x[1])
        for index, row in enumerate(not_selected_songs):
            shuffled_songs.append(row)
        

        window['-TABLE-'].update(values=shuffled_songs)
        #highlight_all_rows(window)


def save_config(file_path=None, ardour_path=None, osc_server_address=None, osc_server_port=None, songfolder=None):
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    debug_print(f"Saving config file: {config_path}")

    # Read existing config file
    existing_config = load_config()
    
    # Update values with provided parameters
    if file_path is not None:
        existing_config['file_path'] = file_path
    if ardour_path is not None:
        existing_config['ardour_path'] = ardour_path
    if osc_server_address is not None:
        existing_config['osc_server_address'] = osc_server_address
    if osc_server_port is not None:
        existing_config['osc_server_port'] = osc_server_port
    if songfolder is not None:
        existing_config['songfolder'] = songfolder

    # Write the entire updated configuration back to the file
    with open(config_path, 'w') as config_file:
        for key, value in existing_config.items():
            config_file.write(f"{key}={value}\n")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    debug_print(f"Loading config file: {config_path}")

    # Read existing config file
    existing_config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r') as existing_config_file:
            for line in existing_config_file:
                key, value = line.strip().split('=')
                existing_config[key.strip()] = value.strip()

    return existing_config

def select_next_song(window, values):
    global songfolder
    table_values = window['-TABLE-'].get()
    # Highlight the next row or jump to the first row if the next index does not exist
    print(values['-TABLE-'])
    if len(values['-TABLE-']) < 1:
        highlighted_row = 1
        next_row = 2
    else:
        highlighted_row = values['-TABLE-'][0] + 2
        next_row = highlighted_row + 1
    
    if highlighted_row >= len(table_values) + 1:
        highlighted_row = 1
    if next_row >= len(table_values) + 2:
        next_row = 2
    if next_row >= len(table_values) + 1:
        next_row = 1
    window['-TABLE-'].Widget.selection_set(highlighted_row)
    window['-TABLE-'].Widget.see(highlighted_row)  # Ensure the highlighted row is visible
    
    # Execute the command
    if values['-STARTARDOUR-']:
        # Get the ardour file name of the currently highlighted row
        command_to_execute = f"{values['-ARDOUR-']} {table_values[highlighted_row-1][9]}"
        debug_print(command_to_execute)
        # subprocess.run([values['-ARDOUR-'], table_values[highlighted_row-1][2]])
        subprocess.run(values['-ARDOUR-'])
    
    #send values via OSC
    songname = table_values[highlighted_row-1][2]
    duration = table_values[highlighted_row-1][3]
    bpm = table_values[highlighted_row-1][4]
    key = table_values[highlighted_row-1][5]
    mood = table_values[highlighted_row-1][6]
    next_songname = table_values[next_row-1][2]
    send_osc_messages(songname, duration, bpm, key, mood, next_songname)

def connect_to_osc_server(osc_server_address, osc_server_port):
    try:
        client = udp_client.SimpleUDPClient(osc_server_address, osc_server_port)
        debug_print(f"Connected to OSC server: {osc_server_address}:{osc_server_port}")
        return client
    except Exception as e:
        sg.popup_error(f"Error connecting to OSC server:\n{e}")
        return None

def receive_osc_message(addr, *args):
    # Replace <Your_OSC_Method> with the appropriate method to call when a message is received
    debug_print(f"Received OSC message: {addr} {args}")
    # <Your_OSC_Method>(*args)

def start_osc_server(port):
    dispatcher = osc_server.Dispatcher()
    dispatcher.set_default_handler(receive_osc_message)
    global stop_threads
    stop_threads = False
    hostname = socket.gethostname()
    debug_print(hostname)
    server = osc_server.ThreadingOSCUDPServer((hostname, port), dispatcher)

    debug_print(f"OSC Server listening on port {port}")

    while not stop_threads:
        # Use select to handle requests with a timeout
        readable, _, _ = select.select([server.socket], [], [], 1.0)
        if readable:
            server.handle_request()

    server.server_close()
    debug_print("OSC Server stopped.")


# Modify the existing start_osc_server_in_thread function
def start_osc_server_in_thread(port):
    osc_thread = Thread(target=start_osc_server, args=[port])
    osc_thread.start()
    return osc_thread

def main_menu():
    return [
        ['&File', ['&Exit']],
        ['&Tools', ['&OSC Connection', 'Send &MIDI PC']],
    ]

def main():
    # Load the last selected file path, Ardour path, and OSC server from the config file
    global songfolder
    config = load_config()
    
    debug_print(f"Last selected file path: {config['file_path']}")
    debug_print(f"Last Ardour path: {config['ardour_path']}")
    debug_print(f"OSC Server Address: {config['osc_server_address']}")
    debug_print(f"OSC Server Port: {config['osc_server_port']}")
    debug_print(f"Song Folder: {config['songfolder']}")
    songfolder = config['songfolder']
    # Band members
    BAND_MEMBERS = ['Gerrit', 'Jan', 'Niko', 'Boris']

    # OSC client
    osc_client = None


    table_values = []

    # Create the menu bar
    menu_def = main_menu()

    # Define the layout for the GUI
    layout = [        
        [sg.MenuBar(menu_def)],
        [sg.Text("Select Ardour program:")],
        [sg.Input(key='-ARDOUR-', default_text=config['ardour_path']), sg.FileBrowse(), sg.Button('Set Ardour Path', key='-SETARDOUR-'), sg.Checkbox('Start Ardour', key='-STARTARDOUR-', default=False)],
        [sg.Text("Select a Setlist:")],
        [sg.Input(key='-FILE-', default_text=config['file_path']), sg.FileBrowse(), sg.Button('Load Setlist', key='-LOADSETLIST-')],
        [sg.Text("Anwesende:")],
        [sg.Checkbox(name, default=True) for name in BAND_MEMBERS],  # Use a loop for the checkboxes
        [sg.Button('Filter and Randomize List', key='-RANDOMIZE-'),
         sg.Button('Start Next Song', key='-HIGHLIGHT-'),
         sg.Button('Select All Rows', key='-HIGHLIGHT-ALL-')],
        [sg.Button('Edit'), sg.Button('Delete Row'),sg.Button('Add Entry'), sg.Button('Move Up'), sg.Button('Move Down')],
        [sg.Table(values=[[]], headings=headings, auto_size_columns=False, col_widths=[10, 20, 15, 20], expand_x=True, expand_y=True, justification='right', num_rows=25, key='-TABLE-',
                  display_row_numbers=False, vertical_scroll_only=False, enable_events=True,
                  select_mode=sg.TABLE_SELECT_MODE_EXTENDED,
                  max_col_width=25)],
        [sg.Button('Exit')]
    ]

    # Create the window
    window = sg.Window('Ardour Rehearsal Manager', layout, size=(800, 600), finalize=True, resizable=True)
    window.Maximize()

    # a double-click to select the row and open an 'edit' window
    window['-TABLE-'].bind("<Double-Button-1>", " Double")
    
    # Set the default file paths if available
    if config['file_path']:
        window['-FILE-'].update(value=config['file_path'])
        read_json_and_display(config['file_path'], window)
    if config['ardour_path']:
        window['-ARDOUR-'].update(value=config['ardour_path'])
    if osc_client:
        window['-OSCADDR-'].update(value=config['osc_server_address'])
        window['-OSCPORT-'].update(value=config['osc_server_port'])

    global osc_thread
    osc_thread = None
    global stop_threads
    # Event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, 'Exit'):
            debug_print("Exiting the program")
            stop_threads = True  # Set the stop flag to signal the OSC thread to stop
            if osc_thread:
                osc_thread.join()  # Wait for the OSC thread to finish

            break
        elif event == 'Send MIDI PC':
            # Open the MIDI dialog
            midi_dialog()
        elif event == 'OSC Connection':
            # Open the OSC dialog
            osc_dialog(config['osc_server_address'],config['osc_server_port'])
        elif event == '-LOADSETLIST-':
            # Handle file path input change
            file_path = values['-FILE-']
            debug_print(f"Selected file: {file_path}")
            save_config(file_path, None, None, None, None)
            read_json_and_display(file_path, window)
        elif event == '-SETARDOUR-':
            # Handle ardour path input change
            ardour_path = values['-ARDOUR-']
            debug_print(f"Selected Ardour path: {ardour_path}")
            save_config(None, ardour_path, None, None, None)
        
        elif event == '-RANDOMIZE-':
            # Shuffle the rows in the table
            shuffle_rows(window, values['-TABLE-'])
        elif event == '-HIGHLIGHT-':
            select_next_song(window, values)
        elif event == '-HIGHLIGHT-ALL-':
            # Highlight all rows in the table
            highlight_all_rows(window)
        
        elif event == 'Edit' or event == '-TABLE- Double':
            selected_indices = values['-TABLE-']
            selected_index = selected_indices[0]
            edit_entry(selected_index, window)
        elif event == 'Delete Row':
            selected_indices = values['-TABLE-']
            delete_rows(window, selected_indices)
        
        elif event == 'Add Entry':
            add_entry(window)
        elif event == 'Move Up':
            selected_indices = values['-TABLE-']
            if selected_indices:
                selected_index = selected_indices[0]
                move_up(window, selected_index)
        elif event == 'Move Down':
            selected_indices = values['-TABLE-']
            if selected_indices:
                selected_index = selected_indices[0]
                move_down(window, selected_index)
        else:
            debug_print(f"Event: {event}")
            debug_print(f"values: {values}")

    # Close the window
    window.close()


if __name__ == "__main__":
    main()
