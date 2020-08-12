from iconservice import *
from .checks import *

TAG = 'SPKT'


class InvalidTreasurer(Exception):
    pass


# An interface of ICON Token Standard, IRC-2
class TokenStandard(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def symbol(self) -> str:
        pass

    @abstractmethod
    def decimals(self) -> int:
        pass

    @abstractmethod
    def totalSupply(self) -> int:
        pass

    @abstractmethod
    def balanceOf(self, _owner: Address) -> int:
        pass

    @abstractmethod
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        pass


# An interface of tokenFallback.
# Receiving SCORE that has implemented this interface can handle
# the receiving or further routine.
class TokenFallbackInterface(InterfaceScore):
    @interface
    def tokenFallback(self, _from: Address, _value: int, _data: bytes):
        pass


class SPKT(IconScoreBase, TokenStandard):

    _NAME = 'name'
    _SYMBOL = 'symbol'
    _DECIMALS = 'decimals'
    _TREASURER = 'treasurer'
    _TREASURY = 'treasury'
    _TOTAL_SUPPLY = 'total_supply'
    _BALANCES = 'balances'

    # ================================================
    #  Event Logs
    # ================================================
    @eventlog(indexed=3)
    def Transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):
        pass

    # ================================================
    #  Initialization
    # ================================================
    def __init__(self, db: IconScoreDatabase) -> None:
        super().__init__(db)
        self._name = VarDB(self._NAME, db, value_type=str)
        self._symbol = VarDB(self._SYMBOL, db, value_type=str)
        self._decimals = VarDB(self._DECIMALS, db, value_type=int)
        self._total_supply = VarDB(self._TOTAL_SUPPLY, db, value_type=int)
        self._balances = DictDB(self._BALANCES, db, value_type=int)
        self._treasurer = VarDB(self._TREASURER, db, value_type=Address)
        self._treasury = VarDB(self._TREASURY, db, value_type=Address)

    def on_install(self, _name: str, _symbol: str, _decimals: int, _initialSupply: int, _treasurer: Address, _treasury: Address) -> None:
        super().on_install()

        if _initialSupply < 0:
            revert("Initial supply cannot be less than zero")

        if _decimals < 0:
            revert("Decimals cannot be less than zero")
        if _decimals > 21:
            revert("Decimals cannot be more than 21")

        total_supply = _initialSupply * 10 ** _decimals
        Logger.debug(f'on_install: total_supply={total_supply}', TAG)

        self._name.set(_name)
        self._symbol.set(_symbol)
        self._decimals.set(_decimals)
        self._total_supply.set(total_supply)
        self._balances[self.msg.sender] = total_supply
        self._treasurer.set(_treasurer)
        self._treasury.set(_treasury)

    def on_update(self, _name: str, _symbol: str, _decimals: int, _initialSupply: int, _treasurer: Address, _treasury: Address) -> None:
        super().on_update()

    # ================================================
    #  IRC2 Internal methods
    # ================================================
    def _transfer(self, _from: Address, _to: Address, _value: int, _data: bytes):
        # Checks the sending value and balance.
        if _value < 0:
            revert("Transferring value cannot be less than zero")
        if self._balances[_from] < _value:
            revert("Out of balance")

        self._balances[_from] = self._balances[_from] - _value
        self._balances[_to] = self._balances[_to] + _value

        if _to.is_contract:
            # If the recipient is SCORE,
            #   then calls `tokenFallback` to hand over control.
            recipient_score = self.create_interface_score(
                _to, TokenFallbackInterface)
            recipient_score.tokenFallback(_from, _value, _data)

        # Emits an event log `Transfer`
        self.Transfer(_from, _to, _value, _data)
        Logger.debug(f'Transfer({_from}, {_to}, {_value}, {_data})', TAG)

    # ================================================
    #  IRC2 Standard external methods
    # ================================================
    @external(readonly=True)
    def name(self) -> str:
        return self._name.get()

    @external(readonly=True)
    def symbol(self) -> str:
        return self._symbol.get()

    @external(readonly=True)
    def decimals(self) -> int:
        return self._decimals.get()

    @external(readonly=True)
    def totalSupply(self) -> int:
        return self._total_supply.get()

    @external(readonly=True)
    def balanceOf(self, _owner: Address) -> int:
        return self._balances[_owner]

    @catch_error
    @external
    def transfer(self, _to: Address, _value: int, _data: bytes = None):
        revert(f'{self._name.get()} is not transferable')

    @catch_error
    @external
    def treasury_withdraw(self, user_address: Address, value: int):
        self._check_treasurer(self.msg.sender)
        self._transfer(self._treasury.get(), user_address, value, b'None')

    @catch_error
    @external
    def treasury_deposit(self, address: Address, value: int):
        self._check_treasurer(self.msg.sender)
        self._transfer(address, self._treasury.get(), value, b'None')

    # ================================================
    #  SPKT Checks
    # ================================================
    def _check_treasurer(self, sender: Address) -> None:
        if sender != self._treasurer.get():
            raise InvalidTreasurer(sender, self._treasurer.get())

    # ================================================
    #  SPKT External methods
    # ================================================
    @external(readonly=True)
    def get_treasurer(self) -> Address:
        return self._treasurer.get()

    @external(readonly=True)
    def get_treasury(self) -> Address:
        return self._treasury.get()

    # ================================================
    #  SPKT Operator methods
    # ================================================
    @catch_error
    @only_owner
    @external
    def set_treasurer(self, address: Address) -> None:
        self._treasurer.set(address)

    @catch_error
    @only_owner
    @external
    def set_treasury(self, address: Address) -> None:
        self._treasury.set(address)

    @catch_error
    @only_owner
    @external
    def operator_transfer(self, _from: Address, _to: Address, _value: int, _data: bytes = None):
        self._transfer(_from, _to, _value, b'None')

    @catch_error
    @only_owner
    @external
    def mint(self, amount: int) -> None:
        self._total_supply.set(self._total_supply.get() + amount)
        self._balances[self.msg.sender] += amount
