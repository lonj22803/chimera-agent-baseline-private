"""Runner de T3 con el exportador suave aplicado antes de arrancar."""
from version_final_reto.investigacion.task_3 import policy

policy.aplicar()

from version_final_reto.task_3.agent.run_task3 import main  # noqa: E402

if __name__ == "__main__":
    main()
