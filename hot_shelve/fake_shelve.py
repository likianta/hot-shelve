class FakeShelve(dict):
    
    @property
    def key_map(self) -> dict:
        return self
    
    def to_dict(self) -> dict:
        return self
    
    def to_internal_dict(self) -> dict:
        return self
    
    def sync(self) -> None:
        pass
    
    def close(self) -> None:
        pass
