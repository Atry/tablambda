# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_28e1dc540c4420ea:
    cap_0: Lambda

    def __call__(self, a):
        return vg_bf62f9c5ab721067(self.cap_0)

@interned
class vg_61b34437d45d82e0:

    def __call__(self, a):
        return a

@interned
class vg_8790df277e7bb93c:

    def __call__(self, a):
        return vg_db9f3128efd034ba(a)

@interned
class vg_9eca90c294b53d2f:

    def __call__(self, a):
        return vg_61b34437d45d82e0()

@interned
class vg_bf62f9c5ab721067:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_9eca90c294b53d2f())

@interned
class vg_db9f3128efd034ba:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_efc1edb62d228094())

@interned
class vg_e561850b8c0a73e6:

    def __call__(self, a):
        return vg_8790df277e7bb93c()

@interned
class vg_efc1edb62d228094:

    def __call__(self, a):
        return vg_28e1dc540c4420ea(a)
compiled = vg_e561850b8c0a73e6()