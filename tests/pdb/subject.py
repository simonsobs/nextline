import asyncio

##__________________________________________________________________||
def f():
    r = 0
    return r

def subject():
    f()
    f()
    return

##__________________________________________________________________||
async def a():
    await asyncio.sleep(0.1)
    return

def run_a():
    asyncio.run(a())

##__________________________________________________________________||
def gen():
    yield 1
    yield 2

def call_gen():
    for _ in gen():
        pass
##__________________________________________________________________||