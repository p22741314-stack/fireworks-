@bot.command(name="restock")
async def restock(ctx):

    if not is_admin(ctx):
        await ctx.send(
            "You do not have permission to use this command."
        )
        return

    if not ctx.message.attachments:
        await ctx.send(
            "Attach a .txt file containing one key per line.\n"
            "Example: .restock + keys.txt"
        )
        return

    attachment = ctx.message.attachments[0]

    if not attachment.filename.lower().endswith(".txt"):
        await ctx.send(
            "The restock file must be a .txt file."
        )
        return

    try:
        file_data = await attachment.read()
        text = file_data.decode("utf-8")

    except Exception:
        await ctx.send(
            "I could not read that file."
        )
        return

    new_keys = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not new_keys:
        await ctx.send(
            "The attached file contains no keys."
        )
        return

    added = 0

    for new_key in new_keys:

        if new_key not in stored_keys:
            stored_keys.append(new_key)
            added += 1

    save_data()

    await ctx.send(
        f"Restocked {added:,} key(s).\n"
        f"Current stock: {len(stored_keys):,} key(s)."
    )
