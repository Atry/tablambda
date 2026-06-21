# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_0d9466a1568d83d9:

    def __call__(self, a):
        return vg_3933d38da884199a(a)

@interned
class vg_3933d38da884199a:
    cap_0: Lambda

    def __call__(self, a):
        return vg_42bbb29921f6faa9(self.cap_0, a)

@interned
class vg_42bbb29921f6faa9:
    cap_0: Lambda
    cap_1: Lambda

    def __call__(self, a):
        return vg_4aaa936c7c8a7097(a, self.cap_0, self.cap_1)

@interned
class vg_4aaa936c7c8a7097:
    cap_0: Lambda
    cap_1: Lambda
    cap_2: Lambda

    def __call__(self, a):
        return Thunk(Thunk(self.cap_0, self.cap_1), self.cap_2)

@interned
class vg_513d3b50ad4efcd5:
    cap_0: Lambda

    def __call__(self, a):
        return self.cap_0

@interned
class vg_61b34437d45d82e0:

    def __call__(self, a):
        return a

@interned
class vg_9eca90c294b53d2f:

    def __call__(self, a):
        return vg_61b34437d45d82e0()

@interned
class vg_ed8877638757d1e5:

    def __call__(self, a):
        return vg_513d3b50ad4efcd5(a)
compiled = Thunk(Thunk(vg_0d9466a1568d83d9(), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))))))), Thunk(Thunk(vg_0d9466a1568d83d9(), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))))))), Thunk(Thunk(vg_0d9466a1568d83d9(), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))))))), Thunk(Thunk(vg_0d9466a1568d83d9(), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))))))), Thunk(Thunk(vg_0d9466a1568d83d9(), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))))))), Thunk(Thunk(vg_0d9466a1568d83d9(), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))))))), vg_9eca90c294b53d2f()))))))