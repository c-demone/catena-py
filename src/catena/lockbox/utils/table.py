from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich import box

import time
from typing import Optional, List, Any, Dict, Type

console = Console()


def clear_screen():
    """
        Clear user window
    """

    print('\x1b[1J')

    return True


def tabulate(cols: List[str], # List of column names
             rows: List[List[Any]], 
             title: Optional[str] = '🧩 Secrets List',
             hideTTL: Optional[int] = 15,
             show_header: Optional[bool] = True,
             header_style: Optional[str] = 'bold turquoise4'):
    
    """
    Create table for displaying results
    """

    class __result:
        """
        Store result and provide method to display
        """

        def __init__(self, table: Type[Table]):

            self.table = table
            self.hideTTL = hideTTL

        
        def display(self):
            """
            Securely display table of secrets
            """
            console.print(self.table)
            time.sleep(hideTTL)
            clear_screen()

    table = Table(show_header=show_header, header_style=header_style)

    table.title = title
    table.box = box.SQUARE_DOUBLE_HEAD

    # add column headers
    for col in cols:
        table.add_column(col)
    
    # add rows
    for row in rows:
        table.add_row(*row)

    table.caption =  '🔐 [gold1]LockBox[/gold1]'

    # center output in console and return result
    centered_table = Align.center(table)
    return __result(centered_table)




if __name__ == '__main__':

    # example usage
    cols = ['Date', 'Title', 'Production Budget', 'Box Office']
    rows = [["Dec 20, 2019", "Star Wars: The Rise of Skywalker", "$275,000,000", "$375,126,118"],
            ["May 25, 2018",
            "[red]Solo[/red]: A Star Wars Story",
            "$275,000,000",
            "$393,151,347"],
            ["Dec 15, 2017",
            "Star Wars Ep. VIII: The Last Jedi",
            "$262,000,000",
            "[bold]$1,332,539,889[/bold]"]
    ]

    table = tabulate(cols, rows)
    table.display()