import random


# --- !dudes command ---
async def dudes(message):
    # All possible types of dudes
    dude_types = [
        "standard", "armored", "elite", "cloaked", "flying", "cursed", "radioactive",
        "bald", "giga", "miniboss", "legendary", "sleepy", "drunk", "invisible",
        "suspicious", "feral", "enchanted", "buffed", "corrupted", "professional",
        "rookie", "tactical", "useless", "shadow", "holy", "hydraulic"
    ]

    # Fun Nightbot-style templates
    responses = [
        "{} dudes have been dispatched.",
        "{} dudes detected.",
        "{} dudes are now en route.",
        "{} dudes are approaching your location.",
        "{} dudes spawning...",
        "{} dudes materialize out of thin air.",
        "Nightbot: {} dudes generated.",
        "Alert: {} dudes are coming. Brace yourself.",
        "Analysis complete: {} dudes confirmed.",
        "Calibrating... {} dudes deployed.",
        "Your request processed: {} dudes.",
        "Quantum jump successful: {} dudes.",
    ]

    # Random dude count logic
    roll = random.random()

    if roll < 0.05:
        # 5% chance of mythic roll
        count = random.randint(500, 10000)
        flavor = "MYTHIC DUDE RIFT OPENED"
    elif roll < 0.10:
        # 5% chance negative dudes appear
        count = random.randint(-20, -1)
        flavor = "system malfunction detected"
    else:
        count = random.randint(0, 150)
        flavor = random.choice(dude_types)

    response_text = random.choice(responses).format(count)

    # Add type flavor
    response_text += f" ({flavor})"

    # Rare chance to also send a funny gif
    if random.random() < 0.08:  # 8% chance
        funny_gifs = [
            "https://media.tenor.com/5iS5C8R7QkEAAAAd/soldiers-running.gif",
            "https://media.tenor.com/T5gEl-0JxR0AAAAC/army.gif",
            "https://media.tenor.com/rV7gkI-F-vMAAAAC/running-dudes.gif",
            "https://media.tenor.com/OH6O5r9H0bEAAAAd/dudes-arriving.gif"
        ]
        await message.channel.send(response_text)
        await message.channel.send(random.choice(funny_gifs))
    else:
        await message.channel.send(response_text)

    return
