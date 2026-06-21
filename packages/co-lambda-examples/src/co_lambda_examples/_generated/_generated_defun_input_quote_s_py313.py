# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_02d30f264d16d60a:

    def __call__(self, a):
        return vg_58f5710b981c8e2f()

@interned
class vg_059d580e4fc33334:

    def __call__(self, a):
        return vg_9b6ac69f277df473()

@interned
class vg_0891695f7ed1554c:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_6374f1d4559fa78a())

@interned
class vg_0d9466a1568d83d9:

    def __call__(self, a):
        return vg_3933d38da884199a(a)

@interned
class vg_13e2270e987b28ce:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, Thunk(Thunk(vg_0d9466a1568d83d9(), vg_9eca90c294b53d2f()), Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f())))

@interned
class vg_14370dc19ddc1729:
    cap_0: Lambda

    def __call__(self, a):
        return vg_13e2270e987b28ce(self.cap_0)

@interned
class vg_178536b540e69b83:

    def __call__(self, a):
        return Thunk(Thunk(a, vg_6abc43ce2bac47cd()), vg_efc1edb62d228094())

@interned
class vg_1972fef9ee27b59c:

    def __call__(self, a):
        return Thunk(Thunk(a, vg_287f1966ac879d24()), vg_efc1edb62d228094())

@interned
class vg_19c9ea5a2c6d68eb:

    def __call__(self, a):
        return vg_6de34b06e53c2aa5()

@interned
class vg_1a091a24807c4b92:

    def __call__(self, a):
        return vg_1e239f546c3ab1c1()

@interned
class vg_1e239f546c3ab1c1:

    def __call__(self, a):
        return vg_178536b540e69b83()

@interned
class vg_287f1966ac879d24:

    def __call__(self, a):
        return vg_14370dc19ddc1729(a)

@interned
class vg_28e1dc540c4420ea:
    cap_0: Lambda

    def __call__(self, a):
        return vg_bf62f9c5ab721067(self.cap_0)

@interned
class vg_368a72245712aa27:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_02d30f264d16d60a())

@interned
class vg_3933d38da884199a:
    cap_0: Lambda

    def __call__(self, a):
        return vg_42bbb29921f6faa9(self.cap_0, a)

@interned
class vg_397a949c34f49e33:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_19c9ea5a2c6d68eb())

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
class vg_58f5710b981c8e2f:

    def __call__(self, a):
        return vg_397a949c34f49e33(a)

@interned
class vg_61b34437d45d82e0:

    def __call__(self, a):
        return a

@interned
class vg_6374f1d4559fa78a:

    def __call__(self, a):
        return vg_8956d82c1678ac40()

@interned
class vg_6abc43ce2bac47cd:

    def __call__(self, a):
        return vg_ea63524f6f1a951d(a)

@interned
class vg_6de34b06e53c2aa5:

    def __call__(self, a):
        return vg_0891695f7ed1554c(a)

@interned
class vg_80adbaa678acfb5c:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, Thunk(Thunk(vg_0d9466a1568d83d9(), vg_ed8877638757d1e5()), vg_9eca90c294b53d2f()))

@interned
class vg_8956d82c1678ac40:

    def __call__(self, a):
        return vg_b1a97bd0cc8361af()

@interned
class vg_9b6ac69f277df473:

    def __call__(self, a):
        return vg_1972fef9ee27b59c()

@interned
class vg_9eca90c294b53d2f:

    def __call__(self, a):
        return vg_61b34437d45d82e0()

@interned
class vg_b1a97bd0cc8361af:

    def __call__(self, a):
        return Thunk(Thunk(a, vg_059d580e4fc33334()), vg_1a091a24807c4b92())

@interned
class vg_bf62f9c5ab721067:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_9eca90c294b53d2f())

@interned
class vg_e3b2461abf6642f0:

    def __call__(self, a):
        return vg_368a72245712aa27(a)

@interned
class vg_ea63524f6f1a951d:
    cap_0: Lambda

    def __call__(self, a):
        return vg_80adbaa678acfb5c(self.cap_0)

@interned
class vg_ed8877638757d1e5:

    def __call__(self, a):
        return vg_513d3b50ad4efcd5(a)

@interned
class vg_efc1edb62d228094:

    def __call__(self, a):
        return vg_28e1dc540c4420ea(a)

@interned
class vg_f85890e26986083e:

    def __call__(self, a):
        return vg_e3b2461abf6642f0()
compiled = vg_f85890e26986083e()