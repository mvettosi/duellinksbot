from discord.ext import commands
import asyncio


def setup(bot):
    bot.add_cog(DevCog(bot))


class DevCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def test(self, context):
        print('Command test received')
        await context.send('Command test received')

    @commands.command()
    async def reload(self, context):
        for extension in self.bot.loaded_extensions:
            self.bot.reload_extension(extension)
