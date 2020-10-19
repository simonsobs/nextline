
##__________________________________________________________________||
async def print_upto_prompt(queue):
    while True:
        m = await queue.get()
        if m is None:
            return True # pdb ended
        print(m, end='')
        if '(Pdb)' in m:
            break

async def control_pdb(commands, queue_in, queue_out):
    for command in commands:
        if await print_upto_prompt(queue_out):
            break
        print(command)
        await queue_in.put(command)
        print(queue_in.put)

##__________________________________________________________________||
