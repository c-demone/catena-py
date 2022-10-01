from PyInquirer import style_from_dict

pass_style= style_from_dict({
    "separator": '#6C6C6C',
    "questionmark": '#FF9D00 bold',
    "selected": '#5F819D',
    "pointer": '#FF9D00 bold',
    "instruction": '',  # default
    "answer": '#5F819D bold',
    "question": '',
})

del_style = style_from_dict({
    "separator": '#cc5454',
    "questionmark": '#673ab7 bold',
    "selected": '#cc5454',  # default
    "pointer": '#673ab7 bold',
    "instruction": '',  # default
    "answer": '#f44336 bold',
    "question": '',
})