"""Runt the service with command:
    poetry run python data_talker/service.py
"""

import asyncio
import os
import threading
import time
from io import StringIO

import dash
import dash_ag_grid as ag
import dash_html_components as html
import dash_table
import pandas as pd
from dash import Input, Output, State, callback, dcc
from df_tool import DataFrameProcessTool
from polymind.core.message import Message
from voice import generate_transcription

# Global flag for recording control
is_recording = threading.Event()
latest_message = ""  # Global variable to hold the transcription text

df: pd.DataFrame = None
df_process_tool = DataFrameProcessTool()
chat_history_df = pd.DataFrame(columns=["Timestamp", "User", "Message"])

app = dash.Dash(
    __name__, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"]
)


def record_and_transcribe():
    """Function to handle the recording and transcription process."""
    global latest_message
    print("Recording...")
    while is_recording.is_set():
        # Place your actual recording and transcription logic here
        user_input = generate_transcription(verbose=False)

        if not user_input:
            # TODO: Ask user to input by changing status-output value
            print("No input detected. Please speak again.")
        elif user_input and user_input != latest_message:
            latest_message = user_input
            print(f"User input: {latest_message}")
        time.sleep(1)  # Simulate time delay for recording
    print("Stopped recording.")


@callback(
    Output("dummy-output", "children"),
    Input("submit-button", "n_clicks"),
    State("requirement-input", "value"),
)
def button_click(n_clicks, user_requirement):
    """Triggered when the submit button is clicked.
    It will update the chat-update-from-text with the user requirement.
    """
    global latest_message
    if user_requirement and user_requirement != latest_message:
        latest_message = user_requirement
    return ""


@callback(
    Output("status-output", "children"),
    Input("voice-input-toggle", "value"),
)
def toggle_voice_input(toggle_values):
    """Triggered when the voice input toggle is changed.
    The function starts or stops the voice recording based on the toggle value.
    The recognized text is stored in the global variable latest_message.

    Args:
        toggle_values (_type_): _description_

    Returns:
        _type_: _description_
    """
    global is_recording
    if "voice_input" in toggle_values:
        if not is_recording.is_set():
            is_recording.set()
            thread = threading.Thread(target=record_and_transcribe)
            thread.start()
            return "Voice recording started. Speak now..."
    else:
        is_recording.clear()
        return "Voice recording stopped."


@callback(
    Output("chat-history-table", "data"),
    Input("interval-component", "n_intervals"),
    State("chat-history-table", "data"),
)
def update_chat_history(n_interval, chat_history_data):
    """Update the chat history table with new chat entries from either text or voice."""
    global latest_message
    new_message = None
    if latest_message:
        new_message = latest_message
        latest_message = ""  # Reset the latest message after processing
        print(f"New message from text: {new_message}")
        new_entry = {
            "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "User": "User",
            "Message": new_message,
        }
        chat_history_data.append(new_entry)
        return chat_history_data
    else:
        return dash.no_update


@callback(
    Output("my-grid", "rowData"),
    Output("my-grid", "columnDefs"),
    Output("requirement-input", "value"),
    Input("chat-history-table", "data"),
)
def update_ag_grid_table(chat_history_data):
    """Get the chat history from latest to oldest and update the AgGrid table."""
    chat_history = chat_history_data[
        ::-1
    ]  # Reverse the chat history to show latest first
    # Construct histroy message that can be easily understand by LLM.
    chat_history_text = "\n".join([entry["Message"] for entry in chat_history])
    input_message = Message(
        content={"user_requirement": chat_history_text, "df_json": df.to_json()}
    )
    output_message = asyncio.run(df_process_tool(input_message))
    output_df_json = output_message.get("output", "")
    output_df = pd.read_json(StringIO(output_df_json))

    print(f"Number of rows: {len(output_df)}")
    output_df_column_defs = [
        {"field": col, "headerName": col} for col in output_df.columns.tolist()
    ]
    output_df_records = output_df.to_dict("records")
    return output_df_records, output_df_column_defs, ""


def create_chat_history_table():
    """Creates a table to display chat history that is scrollable and has controlled column widths."""
    return dash_table.DataTable(
        id="chat-history-table",
        columns=[
            {"name": "Timestamp", "id": "Timestamp"},
            {"name": "User", "id": "User"},
            {"name": "Message", "id": "Message"},
        ],
        data=chat_history_df.to_dict("records"),
        style_table={"height": "100px", "overflowY": "auto"},  # Makes table scrollable
        style_cell={
            "minWidth": "20px",
            "maxWidth": "50px",
            "width": "150px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "padding": "5px",
        },
        style_header={
            "backgroundColor": "lightgrey",
            "fontWeight": "bold",
            "text-align": "center",
        },
        style_data_conditional=[
            # Optional, for further styling based on condition
            {
                "if": {"column_id": "Message"},
                "textAlign": "left",
                "maxWidth": "300px",  # Example of further limiting message column width
            }
        ],
    )


def create_ag_grid_table(df: pd.DataFrame) -> html.Div:
    """Create an interactive AgGrid table with configurable column widths.
    Parameters:
        df (Pandas DataFrame): The DataFrame to display in the table.
    Returns:
        A Dash HTML Div containing the AgGrid table.
    """
    column_defs = [
        {
            "field": col,
            "headerName": col,
        }
        for col in df.columns.tolist()
    ]
    ag_grid = ag.AgGrid(
        id="my-grid",
        columnDefs=column_defs,
        # columnSize="responsiveSizeToFit",
        rowData=df.to_dict("records"),
        rowModelType="clientSide",
        dashGridOptions={
            "pagination": True,
            "paginationPageSize": 100,  # initial page size
            "columnDefs": {
                "resizable": True,  # allow column width resizing
            },
        },
        columnState=[
            {
                "columnBuffer": 1000,  # column width buffer for better performance
            }
        ],
        className="ag-theme-alpine",
    )
    layout = html.Div([ag_grid])
    return layout


def generate_app_layout(table_div: html.Div) -> html.Div:
    chat_history_table = create_chat_history_table()
    layout = html.Div(
        children=[
            html.H1(
                "Talk is NOT cheap, show me your data", style={"textAlign": "center"}
            ),
            table_div,
            html.Br(),
            html.Div(
                children=[
                    dcc.Textarea(
                        id="requirement-input",
                        contentEditable=True,
                        draggable=False,
                        spellCheck=True,
                        style={
                            "width": "90%",
                            "height": "100px",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                        },
                    ),
                    html.Button(
                        "Submit",
                        id="submit-button",
                        n_clicks=0,
                        style={"display": "inline-block", "verticalAlign": "middle"},
                    ),
                ],
                style={"textAlign": "center", "width": "100%"},
            ),
            html.Div(
                children=[
                    html.Label("Enable Voice Input"),
                    dcc.Checklist(
                        id="voice-input-toggle",
                        options=[{"label": "Voice Input", "value": "voice_input"}],
                        value=[],
                    ),
                ],
                style={"textAlign": "center", "marginBottom": "10px"},
            ),
            html.Div(
                id="interval-div",
                children=[
                    dcc.Interval(
                        id="interval-component", interval=1000, n_intervals=0
                    )  # 1-second interval
                ],
            ),
            html.Div(id="status-output", style={"whiteSpace": "pre-line"}),
            html.H2("Chat History", style={"textAlign": "center"}),
            chat_history_table,
            html.Br(),
            html.Div(id="dummy-output", style={"display": "none"}),
        ]
    )
    return layout


def generate_interactive_table(table_div: html.Div):
    """Generate an interactive table using Dash given a Pandas DataFrame.
    Parameters:
        df (Pandas DataFrame): The DataFrame to display in the table.
    """
    app.layout = generate_app_layout(table_div=table_div)
    app.run_server(debug=True)


async def main():
    global df
    csv_path = os.path.join(os.path.dirname(__file__), "../example.csv")
    df = pd.read_csv(csv_path)
    table_div = create_ag_grid_table(df)
    generate_interactive_table(table_div)


if __name__ == "__main__":
    asyncio.run(main())
