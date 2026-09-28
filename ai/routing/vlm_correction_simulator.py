def correct_text_with_vlm_simulation(image_path):
    """
    Simulated VLM correction for pipeline testing.

    This uses predefined ground-truth text only to simulate
    what a successful VLM correction could return.

    This is NOT actual VLM model performance.
    """

    corrections = {
        "image 1.jpg": "MARCO PIERRE WHITE",
        "image 2.jpg": "PANDORA",
        "image 3.jpg": "Dubai English Speaking School",
        "image 4.jpg": "West Suffolk Hospital",
        "image 5.jpg": "Percy Ingle"
    }

    image_name = image_path.replace("\\", "/").split("/")[-1]

    return corrections.get(
        image_name,
        ""
    )