def get_processing_error_message(
    error_type_string, toolname, ex, traceback_str, doing=""
):
    """standard template for generating processing tool error messages"""
    message = f"{error_type_string} occured in processing tool {toolname}"
    if doing:
        message = f"{message} {doing}"
    message = f"{message}: {ex} - {traceback_str}"
