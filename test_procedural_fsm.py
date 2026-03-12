import asyncio
import sys
from manual_to_uml.simulation.compile_endpoint import compile_manual
from fastapi import HTTPException

test_text = """
Step 1 shutdown
Step 2 depressurize
Step 3 inspect
If leak == true replace
Step 4 continue
Step 5 reinstall
Step 6 torque
Step 7 restart
If vibration > 5 abort
Step 8 finalize
"""

async def run_test():
    try:
        response = await compile_manual(manual_text=test_text, file=None)
        print("Success! IBR generated.")
    except HTTPException as e:
        print("======== HTTP EXCEPTION ========")
        print(e.detail)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
