import asyncio
import os
import re
from io import StringIO
from typing import List

import pandas as pd
from polymind.core.logger import Logger
from polymind.core.message import Message
from polymind.core.tool import BaseTool, Param
from polymind.core_tools.llm_tool import OpenAIChatTool


class DataFrameProcessTool(BaseTool):
    """DataFrameProcessTool is a tool to post-process the DataFrame based on user requirement."""

    prompt_template: str = """
    You would need to generate python code to post process the given df based on the user requirement.
    Please note the column description may not be 100% accurate, use your best judgement.
    If the column value looks like numbers, treat them as numbers.
    Please put the generated code into the ```python``` blob.

    You would always assume the the function sketch is:
    ```python
    import pandas as pd
    # Copy df as "processed_df" and then operate on it based on user_requirement

    ```

    For example:
    ```python
    import pandas as pd
    processed_df = df.sort_values(by='name', ascending=True)
    ```

    Now the requirement of the user is as below:
    ---
    {user_requirement}
    ---

    And the schema of this df is as below:
    ---
    {df_schema}
    ---
    """

    def __init__(self, tool_name: str = "df-process-tool", *args, **kwargs):
        descriptions: List[str] = [
            "Post-process the DataFrame based on user requirement.",
            "Generate python code to post-process the DataFrame.",
            "Operate the DataFrame based on the user requirement.",
        ]
        super().__init__(
            tool_name=tool_name, descriptions=descriptions, *args, **kwargs
        )
        self._llm_tool = OpenAIChatTool(tool_name="code-generator")
        self._logger = Logger(__file__)

    def input_spec(self) -> List[Param]:
        return [
            Param(
                name="user_requirement",
                type="str",
                required=True,
                description="The user requirement to post-process the DataFrame.",
                example="Sort the data by column 'name' in ascending order.",
            ),
            Param(
                name="df_json",
                type="str",
                required=True,
                description="The content of the DataFrame.",
                example="{'name': ['Alice', 'Bob'], 'age': [25, 30]}",
            ),
        ]

    def output_spec(self) -> List[Param]:
        return [
            Param(
                name="output",
                type="str",
                required=True,
                description="The post-processed df in json.",
                example="{'name': ['Alice', 'Bob'], 'age': [25, 30]}",
            ),
        ]

    async def _gen_code(self, user_requirement: str, df_schema: dict) -> str:
        """Generate the code to post-process the DataFrame based on user requirement."""
        prompt = self.prompt_template.format(
            user_requirement=user_requirement, df_schema=df_schema
        )
        message = Message(content={"input": prompt})
        response_message = await self._llm_tool(message)
        response_text = response_message.get("output", "")
        self._logger.info(f"Generated code: {response_text}")

        match = re.search(r"```python\n(.*)\n```", response_text, re.DOTALL)
        if match:
            code = match.group(1)
        else:
            code = response_text
        self._logger.info(f"Extracted code: {code}")
        return code

    async def _run_code_on_df(self, code: str, df: pd.DataFrame) -> str:
        """Run the code on the DataFrame."""
        local_env = {"df": df}  # Local dictionary to store the environment
        try:
            exec(code, {}, local_env)  # Execute the code in the local environment
            processed_df = local_env[
                "processed_df"
            ]  # Assume the processed df is stored in the local environment
            return processed_df
        except Exception as e:
            self._logger.error(f"Error executing code: {e}")
            raise e  # Or handle it as needed

    async def _execute(self, input: Message) -> Message:
        """Execute the tool to post-process the DataFrame based on user requirement."""
        user_requirement = input.get("user_requirement", "")
        df_json = input.get("df_json", "")
        df = pd.read_json(
            StringIO(df_json)
        )  # Figure out the schema from the df json string
        df_schema = str(df.dtypes.to_dict())
        code = await self._gen_code(
            user_requirement=user_requirement, df_schema=df_schema
        )
        processed_df = await self._run_code_on_df(code=code, df=df)
        processed_df_json = processed_df.to_json()
        return Message(content={"output": processed_df_json})


async def main():
    df_process_tool = DataFrameProcessTool()
    filepath = os.path.join(os.path.dirname(__file__), "../example.csv")
    df = pd.read_csv(filepath)
    df_json = df.to_json()
    filter_by_dau_message = Message(
        content={
            "user_requirement": "Find the top 100 records by GDPU and sort by population desc. Only keep 11.",
            "df_json": df_json,
        }
    )
    output_message = await df_process_tool(filter_by_dau_message)
    output_df_json = output_message.get("output", "")
    output_df = pd.read_json(output_df_json)
    print(output_df.head(100))
    print(f"Number of rows: {len(output_df)}")


if __name__ == "__main__":
    asyncio.run(main())
