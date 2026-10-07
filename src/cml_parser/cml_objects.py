from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Set
import json

class Commented:
    """Mixin providing comment/tag accessors for block-level CML objects.

    Concrete dataclasses declare the fields themselves:
        leading_comment: Optional[str] = None
        inner_comment: Optional[str] = None
        _doc_tags: Dict[str, List[str]] = field(default_factory=dict)
    """

    def get_tag(self, key: str) -> Optional[str]:
        values = self._doc_tags.get(key)
        return values[0] if values else None

    def get_tags(self, key: str) -> List[str]:
        return list(self._doc_tags.get(key, []))

    def has_tag(self, key: str, value: str) -> bool:
        return value in self._doc_tags.get(key, [])

    def has_tags(self, tags: Dict[str, str]) -> bool:
        return all(self.has_tag(key, value) for key, value in tags.items())

class RelationshipType(str, Enum):
    CUSTOMER_SUPPLIER = "Customer-Supplier"
    UPSTREAM_DOWNSTREAM = "Upstream-Downstream"
    DOWNSTREAM_UPSTREAM = "Downstream-Upstream"
    PARTNERSHIP = "Partnership"
    SHARED_KERNEL = "Shared-Kernel"
    ACL = "ACL"
    CF = "CF"
    OHS = "OHS"
    PL = "PL"
    SK = "SK"
    U = "U"
    D = "D"
    S = "S"
    C = "C"
    P = "P"

class SubdomainType(str, Enum):
    UNDEFINED = "UNDEFINED"
    CORE = "CORE_DOMAIN"
    SUPPORTING = "SUPPORTING_DOMAIN"
    GENERIC = "GENERIC_SUBDOMAIN"

@dataclass
class Diagnostic:
    message: str
    line: Optional[int] = None
    col: Optional[int] = None
    filename: Optional[str] = None
    expected: Optional[List[str]] = None
    context: Optional[str] = None

    def pretty(self) -> str:
        location = ""
        if self.filename:
            location += f"{self.filename}"
        if self.line is not None:
            location += f":{self.line}"
            if self.col is not None:
                location += f":{self.col}"
        if location:
            location = f"[{location}] "
        expected = f" (expected: {', '.join(self.expected)})" if self.expected else ""
        return f"{location}{self.message}{expected}"

@dataclass
class ParseResult:
    model: Optional[Any]
    errors: List[Diagnostic]
    warnings: List[Diagnostic]
    source: Optional[str] = None
    filename: Optional[str] = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [asdict(e) for e in self.errors],
            "warnings": [asdict(w) for w in self.warnings],
            "filename": self.filename,
        }

    def __repr__(self):
        status = "OK" if self.ok else "ERROR"
        parts = [status]
        if self.filename:
            parts.append(f"file={Path(self.filename).name}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        if self.warnings:
            parts.append(f"warnings={len(self.warnings)}")
        return f"<ParseResult {' '.join(parts)}>"

# Tactical DDD Objects - Attributes and Operations

@dataclass
class Parameter:
    """Represents a parameter in an operation/method."""
    name: str
    type: str
    is_reference: bool = False  # True if prefixed with @

    def __repr__(self):
        ref_prefix = "@" if self.is_reference else ""
        return f"{ref_prefix}{self.type} {self.name}"

@dataclass
class Operation:
    """Represents an operation/method in a domain object or service."""
    name: str
    return_type: Optional[str] = None
    parameters: List[Parameter] = field(default_factory=list)
    visibility: Optional[str] = None  # public, private, protected
    throws: List[str] = field(default_factory=list)
    is_abstract: bool = False
    hint: Optional[str] = None  # read-only / write
    hint_text: Optional[str] = None
    state_transition: Optional[str] = None
    publishes_to: Optional[str] = None
    subscribes_to: Optional[str] = None
    publishes_event_type: Optional[str] = None
    subscribes_event_type: Optional[str] = None
    publishes_event_bus: Optional[str] = None
    subscribes_event_bus: Optional[str] = None
    http_method: Optional[str] = None
    path: Optional[str] = None
    return_string: Optional[str] = None
    cache: bool = False
    gap: bool = False
    nogap: bool = False
    construct: bool = False
    build: bool = False
    map_flag: bool = False
    query: Optional[str] = None
    condition: Optional[str] = None
    select: Optional[str] = None
    group_by: Optional[str] = None
    order_by: Optional[str] = None
    delegate_target: Optional[str] = None
    delegate_holder_ref: Optional[Any] = field(default=None, repr=False)
    delegate_operation_ref: Optional['Operation'] = field(default=None, repr=False)
    publishes_event_type_ref: Optional[Any] = field(default=None, repr=False)
    subscribes_event_type_ref: Optional[Any] = field(default=None, repr=False)

    def __repr__(self):
        params_str = ", ".join(str(p) for p in self.parameters)
        return_str = f" -> {self.return_type}" if self.return_type else ""
        return f"<Operation({self.name}({params_str}){return_str})>"

@dataclass
class Attribute:
    """Represents an attribute in a domain object (Entity, ValueObject, etc.)."""
    name: str
    type: str
    is_reference: bool = False  # True if prefixed with -
    visibility: Optional[str] = None  # public, private, protected
    is_key: bool = False
    collection_type: Optional[str] = None  # List, Set, Bag, Collection
    required: bool = False
    not_empty: bool = False
    not_blank: bool = False
    nullable: bool = False
    unique: bool = False
    index: bool = False
    changeable: bool = False
    pattern: Optional[str] = None
    size: Optional[str] = None
    min: Optional[str] = None
    max: Optional[str] = None
    digits: Optional[str] = None
    email: bool = False
    email_message: Optional[str] = None
    future: bool = False
    future_message: Optional[str] = None
    past: bool = False
    past_message: Optional[str] = None
    length: Optional[str] = None
    range: Optional[str] = None
    script_assert: Optional[str] = None
    url: Optional[str] = None
    hint: Optional[str] = None
    credit_card: Optional[str] = None
    assert_true: Optional[str] = None
    assert_false: Optional[str] = None
    nullable_message: Optional[str] = None
    not_empty_message: Optional[str] = None
    not_blank_message: Optional[str] = None
    valid_message: Optional[str] = None
    cascade: Optional[str] = None
    fetch: Optional[str] = None
    database_column: Optional[str] = None
    database_type: Optional[str] = None
    database_join_table: Optional[str] = None
    database_join_column: Optional[str] = None
    order_column: Optional[str] = None
    validate: Optional[str] = None
    order_by: Optional[str] = None
    opposite: Optional[str] = None
    decimal_max: Optional[str] = None
    decimal_min: Optional[str] = None
    cache: Optional[bool] = None
    inverse: Optional[bool] = None
    transient: bool = False
    valid: bool = False
    association_label: Optional[str] = None

    def __repr__(self):
        ref_prefix = "-" if self.is_reference else ""
        key_suffix = " key" if self.is_key else ""
        return f"{ref_prefix}{self.type} {self.name}{key_suffix}"

@dataclass
class Association:
    target: str
    is_reference: bool = False
    description: Optional[str] = None
    target_ref: Optional[Any] = field(default=None, repr=False)

    def __repr__(self):
        return f"<Association({self.target})>"

# Domain Objects

@dataclass
class Entity(Commented):
    """Represents an attribute in a domain object (Entity, ValueObject, etc.)."""
    name: str
    is_aggregate_root: bool = False
    attributes: List[Attribute] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    extends: Optional[str] = None
    extends_ref: Optional['Entity'] = field(default=None, repr=False)
    is_abstract: bool = False
    aggregate: Optional['Aggregate'] = field(default=None, repr=False)
    traits: List[str] = field(default_factory=list)
    belongs_to: Optional[str] = None
    belongs_to_ref: Optional[Any] = field(default=None, repr=False)
    validate: Optional[str] = None
    inheritance_type: Optional[str] = None
    discriminator_column: Optional[str] = None
    discriminator_value: Optional[str] = None
    discriminator_type: Optional[str] = None
    discriminator_length: Optional[str] = None
    database_table: Optional[str] = None
    package: Optional[str] = None
    auditable: bool = False
    optimistic_locking: bool = False
    immutable: bool = False
    cache: bool = False
    gap_class: bool = False
    nogap_class: bool = False
    scaffold: bool = False
    hint: Optional[str] = None

    def get_attribute(self, attr_name: str) -> Optional[Attribute]:
        return next((a for a in self.attributes if a.name == attr_name), None)
    
    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        root_suffix = " (root)" if self.is_aggregate_root else ""
        return f"<Entity({self.name}{root_suffix})>"

@dataclass
class ValueObject(Commented):
    """Represents a DDD Value Object."""
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    extends: Optional[str] = None
    extends_ref: Optional['ValueObject'] = field(default=None, repr=False)
    is_abstract: bool = False
    traits: List[str] = field(default_factory=list)
    belongs_to: Optional[str] = None
    belongs_to_ref: Optional[Any] = field(default=None, repr=False)
    package: Optional[str] = None
    validate: Optional[str] = None
    is_aggregate_root: bool = False
    immutable: bool = False
    persistent: bool = False
    cache: bool = False
    optimistic_locking: bool = False
    database_table: Optional[str] = None
    gap_class: bool = False
    nogap_class: bool = False
    scaffold: bool = False
    hint: Optional[str] = None
    inheritance_type: Optional[str] = None
    discriminator_column: Optional[str] = None
    discriminator_value: Optional[str] = None
    discriminator_type: Optional[str] = None
    discriminator_length: Optional[str] = None

    def get_attribute(self, attr_name: str) -> Optional[Attribute]:
        return next((a for a in self.attributes if a.name == attr_name), None)
    
    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<ValueObject({self.name})>"

@dataclass
class DomainEvent(Commented):
    """Represents a DDD Domain Event."""
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    extends: Optional[str] = None
    extends_ref: Optional['DomainEvent'] = field(default=None, repr=False)
    traits: List[str] = field(default_factory=list)
    is_aggregate_root: bool = False
    persistent: bool = False
    is_abstract: bool = False
    belongs_to: Optional[str] = None
    belongs_to_ref: Optional[Any] = field(default=None, repr=False)
    package: Optional[str] = None
    validate: Optional[str] = None
    cache: bool = False
    database_table: Optional[str] = None
    gap_class: bool = False
    nogap_class: bool = False
    scaffold: bool = False
    hint: Optional[str] = None
    inheritance_type: Optional[str] = None
    discriminator_column: Optional[str] = None
    discriminator_value: Optional[str] = None
    discriminator_type: Optional[str] = None
    discriminator_length: Optional[str] = None

    def get_attribute(self, attr_name: str) -> Optional[Attribute]:
        return next((a for a in self.attributes if a.name == attr_name), None)
    
    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<DomainEvent({self.name})>"

@dataclass
class BasicType(Commented):
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    belongs_to: Optional[str] = None
    belongs_to_ref: Optional[Any] = field(default=None, repr=False)
    package: Optional[str] = None
    validate: Optional[str] = None
    immutable: bool = False
    cache: bool = False
    gap_class: bool = False
    nogap_class: bool = False
    hint: Optional[str] = None

    def get_attribute(self, attr_name: str) -> Optional[Attribute]:
        return next((a for a in self.attributes if a.name == attr_name), None)

    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<BasicType({self.name})>"

@dataclass
class Enum(Commented):
    """Represents an enumeration."""
    name: str
    values: List[str] = field(default_factory=list)
    is_aggregate_lifecycle: bool = False
    package: Optional[str] = None
    hint: Optional[str] = None
    ordinal: bool = False
    attributes: List[Attribute] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        lifecycle_suffix = " (lifecycle)" if self.is_aggregate_lifecycle else ""
        return f"<Enum({self.name}{lifecycle_suffix})>"

@dataclass
class Subdomain(Commented):
    name: str
    type: SubdomainType
    vision: str
    domain: 'Domain' = field(default=None, repr=False) # Avoid recursion in repr
    entities: List[Entity] = field(default_factory=list)
    services: List['Service'] = field(default_factory=list)
    implementations: List['Context'] = field(default_factory=list, repr=False)
    supported_requirements: List[Any] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_entity(self, entity_name: str) -> Optional[Entity]:
        return next((e for e in self.entities if e.name == entity_name), None)

    def get_implementation(self, context_name: str) -> Optional['Context']:
        return next((c for c in self.implementations if c.name == context_name), None)

    def __repr__(self):
        return f"<Subdomain({self.name})>"

@dataclass
class Domain(Commented):
    name: str
    vision: str
    subdomains: List[Subdomain] = field(default_factory=list)
    implementations: List["Context"] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def core(self) -> List[Subdomain]:
        return [s for s in self.subdomains if s.type == SubdomainType.CORE]

    @property
    def supporting(self) -> List[Subdomain]:
        return [s for s in self.subdomains if s.type == SubdomainType.SUPPORTING]

    @property
    def generic(self) -> List[Subdomain]:
        return [s for s in self.subdomains if s.type == SubdomainType.GENERIC]

    def get_subdomain(self, subdomain_name: str) -> Optional[Subdomain]:
        return next((s for s in self.subdomains if s.name == subdomain_name), None)

    def __repr__(self):
        return f"<Domain({self.name})>"

@dataclass
class Aggregate(Commented):
    name: str
    owner: Optional[str] = None
    owner_ref: Optional['Context'] = field(default=None, repr=False)
    responsibilities: str = ""
    knowledge_level: str = ""
    user_requirements: List[Any] = field(default_factory=list)
    likelihood_for_change: Optional[str] = None
    content_volatility: Optional[str] = None
    availability_criticality: Optional[str] = None
    consistency_criticality: Optional[str] = None
    storage_similarity: Optional[str] = None
    security_criticality: Optional[str] = None
    security_zone: Optional[str] = None
    security_access_group: Optional[str] = None
    entities: List[Entity] = field(default_factory=list)
    value_objects: List[ValueObject] = field(default_factory=list)
    domain_events: List[DomainEvent] = field(default_factory=list)
    basic_types: List[BasicType] = field(default_factory=list)
    services: List['Service'] = field(default_factory=list)
    resources: List['Resource'] = field(default_factory=list)
    consumers: List['Consumer'] = field(default_factory=list)
    repositories: List['Repository'] = field(default_factory=list)
    enums: List[Enum] = field(default_factory=list)
    command_events: List['CommandEvent'] = field(default_factory=list)
    data_transfer_objects: List['DataTransferObject'] = field(default_factory=list)
    context: Optional['Context'] = field(default=None, repr=False)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_entity(self, entity_name: str) -> Optional[Entity]:
        return next((e for e in self.entities if e.name == entity_name), None)
    
    def get_value_object(self, vo_name: str) -> Optional[ValueObject]:
        return next((vo for vo in self.value_objects if vo.name == vo_name), None)
    
    def get_domain_event(self, event_name: str) -> Optional[DomainEvent]:
        return next((e for e in self.domain_events if e.name == event_name), None)
    
    def get_service(self, service_name: str) -> Optional['Service']:
        return next((s for s in self.services if s.name == service_name), None)
    
    def get_repository(self, repo_name: str) -> Optional['Repository']:
        return next((r for r in self.repositories if r.name == repo_name), None)
    
    def get_enum(self, enum_name: str) -> Optional[Enum]:
        return next((e for e in self.enums if e.name == enum_name), None)

    def __repr__(self):
        return f"<Aggregate({self.name})>"

@dataclass
class Service(Commented):
    name: str
    operations: List[Operation] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    aggregate: Optional[Aggregate] = field(default=None, repr=False)
    gap_class: bool = False
    nogap_class: bool = False
    hint: Optional[str] = None
    subscribe_to: Optional[str] = None
    subscribe_event_bus: Optional[str] = None
    webservice: bool = False
    scaffold: bool = False
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    def __repr__(self):
        return f"<Service({self.name})>"

@dataclass
class Resource(Commented):
    name: str
    operations: List[Operation] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    aggregate: Optional[Aggregate] = field(default=None, repr=False)
    gap_class: bool = False
    nogap_class: bool = False
    scaffold: bool = False
    hint: Optional[str] = None
    path: Optional[str] = None
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    def __repr__(self):
        return f"<Resource({self.name})>"

@dataclass
class Consumer(Commented):
    name: str
    aggregate: Optional[Aggregate] = field(default=None, repr=False)
    hint: Optional[str] = None
    unmarshall_to: Optional[str] = None
    unmarshall_to_ref: Optional[Any] = field(default=None, repr=False)
    queue_name: Optional[str] = None
    topic_name: Optional[str] = None
    subscribe_to: Optional[str] = None
    subscribe_event_bus: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<Consumer({self.name})>"

@dataclass
class Repository(Commented):
    """Represents a DDD Repository for data access."""
    name: str
    operations: List[Operation] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    entity: Optional[Entity] = field(default=None, repr=False)
    gap_class: bool = False
    nogap_class: bool = False
    hint: Optional[str] = None
    subscribe_to: Optional[str] = None
    subscribe_event_bus: Optional[str] = None
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_operation(self, op_name: str) -> Optional[Operation]:
        return next((o for o in self.operations if o.name == op_name), None)

    def __repr__(self):
        return f"<Repository({self.name})>"

@dataclass
class Context(Commented):
    name: str
    type: str = "FEATURE"
    state: str = "UNDEFINED"
    vision: str = ""
    responsibilities: str = ""
    implementation_technology: str = ""
    knowledge_level: str = ""
    business_model: str = ""
    evolution: str = ""
    realizes: List[str] = field(default_factory=list)
    refines: Optional[str] = None
    realizes_refs: List['Context'] = field(default_factory=list, repr=False)
    refines_ref: Optional['Context'] = field(default=None, repr=False)
    implements: List[Any] = field(default_factory=list)
    context_map: Optional['ContextMap'] = field(default=None, repr=False)
    aggregates: List[Aggregate] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)
    consumers: List[Consumer] = field(default_factory=list)
    modules: List['Module'] = field(default_factory=list)
    application: Optional['Application'] = field(default=None, repr=False)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_subdomain(self, subdomain_name: str) -> Optional[Subdomain]:
        return next((s for s in self.implements if s.name == subdomain_name), None)

    def get_aggregate(self, aggregate_name: str) -> Optional[Aggregate]:
        return next((a for a in self.aggregates if a.name == aggregate_name), None)

    def get_service(self, service_name: str) -> Optional[Service]:
        return next((s for s in self.services if s.name == service_name), None)

    def get_resource(self, resource_name: str) -> Optional[Resource]:
        return next((r for r in self.resources if r.name == resource_name), None)

    def get_consumer(self, consumer_name: str) -> Optional[Consumer]:
        return next((c for c in self.consumers if c.name == consumer_name), None)

    def __repr__(self):
        return f"<BoundedContext({self.name})>"

@dataclass
class Relationship:
    left: Context
    right: Context
    type: str = "Unknown"
    roles: List[str] = field(default_factory=list)
    name: Optional[str] = None
    connection: Optional[str] = None
    upstream: Optional[Context] = field(default=None, repr=False)
    downstream: Optional[Context] = field(default=None, repr=False)
    upstream_roles: List[str] = field(default_factory=list)
    downstream_roles: List[str] = field(default_factory=list)
    implementation_technology: Optional[str] = None
    downstream_rights: Optional[str] = None
    exposed_aggregates: List[str] = field(default_factory=list)
    exposed_aggregate_refs: List[Aggregate] = field(default_factory=list, repr=False)
    raw_model: Optional[Any] = field(default=None, repr=False) # The underlying textX object for detailed inspection if needed

    def __repr__(self):
        return f"<Relationship({self.left.name} -> {self.right.name} [{self.type}])>"

@dataclass
class ContextMap(Commented):
    name: str
    type: str
    state: str
    contexts: List[Context] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_context(self, context_name: str) -> Optional[Context]:
        return next((c for c in self.contexts if c.name == context_name), None)

    def get_context_relationships(self, context_name: str) -> List[Relationship]:
        return [
            r for r in self.relationships
            if r.left.name == context_name or r.right.name == context_name
        ]

    def get_relationships_by_type(self, relationship_type: Union[str, RelationshipType]) -> List[Relationship]:
        if isinstance(relationship_type, RelationshipType):
            rtype = relationship_type.value
        else:
            rtype = str(relationship_type)
        
        # Normalize for comparison (simple case-insensitive check)
        rtype = rtype.upper()
        
        results = []
        for r in self.relationships:
            # Check primary type
            if r.type.upper() == rtype:
                results.append(r)
                continue
            
            # Check roles
            if rtype in [role.upper() for role in r.roles]:
                results.append(r)
                continue
                
        return results

    def get_relationship(self, context1: str, context2: str) -> Optional[Relationship]:
        return next(
            (r for r in self.relationships 
             if {r.left.name, r.right.name} == {context1, context2}),
            None
        )

    def __repr__(self):
        return f"<ContextMap({self.name})>"

@dataclass
class UseCase(Commented):
    name: str
    actor: Optional[str] = None
    secondary_actors: List[str] = field(default_factory=list)
    interactions: List[str] = field(default_factory=list)
    benefit: Optional[str] = None
    scope: Optional[str] = None
    level: Optional[str] = None
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<UseCase({self.name})>"

@dataclass
class UserStory(Commented):
    name: str
    role: Optional[str] = None
    feature: Optional[str] = None
    features: List[str] = field(default_factory=list)
    benefit: Optional[str] = None
    split_by: Optional[str] = None
    promoted_values: List[str] = field(default_factory=list)
    harmed_values: List[str] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<UserStory({self.name})>"

@dataclass
class Stakeholder:
    name: str
    influence: Optional[str] = None
    interest: Optional[str] = None
    priority: Optional[str] = None
    impact: Optional[str] = None
    description: Optional[str] = None
    consequences: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"<Stakeholder({self.name})>"

@dataclass
class StakeholderGroup:
    name: str
    stakeholders: List[Stakeholder] = field(default_factory=list)

    def __repr__(self):
        return f"<StakeholderGroup({self.name})>"

@dataclass
class StakeholderSection:
    contexts: List[str] = field(default_factory=list)
    contexts_refs: List['Context'] = field(default_factory=list, repr=False)
    stakeholder_groups: List[StakeholderGroup] = field(default_factory=list)
    stakeholders: List[Stakeholder] = field(default_factory=list)

    def __repr__(self):
        targets = ", ".join(self.contexts) if self.contexts else "*"
        return f"<Stakeholders({targets})>"

@dataclass
class ValueAction:
    action: str
    type: Optional[str] = None

    def __repr__(self):
        return f"<ValueAction({self.action})>"

@dataclass
class ValueConsequence:
    kind: str  # good, bad, neutral
    consequence: str
    action: Optional[ValueAction] = None

    def __repr__(self):
        return f"<ValueConsequence({self.kind}: {self.consequence})>"

@dataclass
class ValueElicitation:
    stakeholder: str
    stakeholder_ref: Optional[Any] = field(default=None, repr=False)
    priority: Optional[str] = None
    impact: Optional[str] = None
    consequences: List[ValueConsequence] = field(default_factory=list)

    def __repr__(self):
        return f"<ValueElicitation({self.stakeholder})>"

@dataclass
class Value:
    name: str
    is_core: bool = False
    demonstrator: Optional[str] = None
    demonstrators: List[str] = field(default_factory=list)
    related_values: List[str] = field(default_factory=list)
    opposing_values: List[str] = field(default_factory=list)
    elicitations: List[ValueElicitation] = field(default_factory=list)
    stakeholders: List[Stakeholder] = field(default_factory=list)

    def __repr__(self):
        return f"<Value({self.name})>"

@dataclass
class ValueCluster:
    name: str
    core_value: Optional[str] = None
    demonstrator: Optional[str] = None
    demonstrators: List[str] = field(default_factory=list)
    related_values: List[str] = field(default_factory=list)
    opposing_values: List[str] = field(default_factory=list)
    elicitations: List[ValueElicitation] = field(default_factory=list)
    values: List[Value] = field(default_factory=list)

    def __repr__(self):
        return f"<ValueCluster({self.name})>"

@dataclass
class ValueRegister(Commented):
    name: str
    context: Optional[str] = None # The context this register is for
    context_ref: Optional[Context] = field(default=None, repr=False)
    clusters: List[ValueCluster] = field(default_factory=list)
    values: List[Value] = field(default_factory=list)
    epics: List['ValueEpic'] = field(default_factory=list)
    weightings: List['ValueWeigthing'] = field(default_factory=list)
    narratives: List['ValueNarrative'] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<ValueRegister({self.name})>"

@dataclass
class Command:
    name: str
    
    def __repr__(self):
        return f"<Command({self.name})>"

@dataclass
class FlowStep:
    type: str # command, event, operation
    name: str
    delegate: Optional[str] = None
    delegate_state_transition: Optional[str] = None
    delegate_ref: Optional[Aggregate] = field(default=None, repr=False)
    emits: List[str] = field(default_factory=list)
    emit_connectors: List[str] = field(default_factory=list)
    emit_refs: List[DomainEvent] = field(default_factory=list, repr=False)
    triggers: List[str] = field(default_factory=list) # For events
    trigger_connectors: List[str] = field(default_factory=list)
    trigger_refs: List[DomainEvent] = field(default_factory=list, repr=False)
    invocations: List[str] = field(default_factory=list)
    invocation_kinds: List[Optional[str]] = field(default_factory=list)
    invocation_connectors: List[str] = field(default_factory=list)
    invocation_command_refs: List[Optional['CommandEvent']] = field(default_factory=list, repr=False)
    invocation_operation_refs: List[Optional[Operation]] = field(default_factory=list, repr=False)
    initiated_by: Optional[str] = None
    command_ref: Optional['CommandEvent'] = field(default=None, repr=False)
    operation_ref: Optional[Operation] = field(default=None, repr=False)

    def __repr__(self):
        return f"<FlowStep({self.type}: {self.name})>"

@dataclass
class Flow:
    name: str
    steps: List[FlowStep] = field(default_factory=list)

    def __repr__(self):
        return f"<Flow({self.name})>"

@dataclass
class Coordination:
    name: str
    steps: List[str] = field(default_factory=list) # List of coordination paths
    step_refs: List['CoordinationStepRef'] = field(default_factory=list, repr=False)

    def __repr__(self):
        return f"<Coordination({self.name})>"

@dataclass
class CoordinationStepRef:
    bounded_context: str
    service: str
    operation: str
    bounded_context_ref: Optional['Context'] = field(default=None, repr=False)
    service_ref: Optional[Service] = field(default=None, repr=False)
    operation_ref: Optional[Operation] = field(default=None, repr=False)

@dataclass
class Application(Commented):
    name: Optional[str] = None
    commands: List[Command] = field(default_factory=list)
    command_events: List['CommandEvent'] = field(default_factory=list)
    domain_events: List['DomainEvent'] = field(default_factory=list)
    flows: List[Flow] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    coordinations: List[Coordination] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return "<Application>"

@dataclass
class CommandEvent(Commented):
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list) # Usually empty for events but allowed by grammar
    extends: Optional[str] = None
    extends_ref: Optional['CommandEvent'] = field(default=None, repr=False)
    is_abstract: bool = False
    traits: List[str] = field(default_factory=list)
    is_aggregate_root: bool = False
    persistent: bool = False
    belongs_to: Optional[str] = None
    belongs_to_ref: Optional[Any] = field(default=None, repr=False)
    package: Optional[str] = None
    validate: Optional[str] = None
    cache: bool = False
    database_table: Optional[str] = None
    gap_class: bool = False
    nogap_class: bool = False
    scaffold: bool = False
    hint: Optional[str] = None
    inheritance_type: Optional[str] = None
    discriminator_column: Optional[str] = None
    discriminator_value: Optional[str] = None
    discriminator_type: Optional[str] = None
    discriminator_length: Optional[str] = None

    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_attribute(self, attr_name: str) -> Optional[Attribute]:
        return next((a for a in self.attributes if a.name == attr_name), None)

    def __repr__(self):
        return f"<CommandEvent({self.name})>"

@dataclass
class DataTransferObject(Commented):
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    extends: Optional[str] = None
    extends_ref: Optional['DataTransferObject'] = field(default=None, repr=False)
    is_abstract: bool = False
    package: Optional[str] = None
    validate: Optional[str] = None
    gap_class: bool = False
    nogap_class: bool = False
    scaffold: bool = False
    hint: Optional[str] = None

    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def get_attribute(self, attr_name: str) -> Optional[Attribute]:
        return next((a for a in self.attributes if a.name == attr_name), None)

    def __repr__(self):
        return f"<DataTransferObject({self.name})>"

@dataclass
class Module(Commented):
    name: str
    external: bool = False
    base_package: Optional[str] = None
    hint: Optional[str] = None
    aggregates: List[Aggregate] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)
    consumers: List[Consumer] = field(default_factory=list)
    domain_objects: List[Any] = field(default_factory=list) # Entities, VOs, etc.
    application: Optional[Application] = field(default=None, repr=False)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)
    
    def __repr__(self):
        return f"<Module({self.name})>"

@dataclass
class TacticDDDApplication(Commented):
    name: str
    base_package: Optional[str] = None
    services: List[Service] = field(default_factory=list)
    resources: List[Resource] = field(default_factory=list)
    consumers: List[Consumer] = field(default_factory=list)
    domain_objects: List[Any] = field(default_factory=list)
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<TacticDDDApplication({self.name})>"

@dataclass
class Trait(Commented):
    name: str
    attributes: List[Attribute] = field(default_factory=list)
    associations: List[Association] = field(default_factory=list)
    operations: List[Operation] = field(default_factory=list)
    package: Optional[str] = None
    hint: Optional[str] = None
    leading_comment: Optional[str] = None
    inner_comment: Optional[str] = None
    _doc_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __repr__(self):
        return f"<Trait({self.name})>"

@dataclass
class ValueEpic:
    name: str
    stakeholder: Optional[str] = None
    stakeholder_ref: Optional[Any] = field(default=None, repr=False)
    value: Optional[str] = None
    realized: List[str] = field(default_factory=list)
    reduced: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"<ValueEpic({self.name})>"

@dataclass
class ValueNarrative:
    name: str
    feature: Optional[str] = None
    promoted: Optional[str] = None
    harmed: Optional[str] = None
    behavior: Optional[str] = None

    def __repr__(self):
        return f"<ValueNarrative({self.name})>"

@dataclass
class ValueWeigthing:
    name: str
    stakeholder: Optional[str] = None
    stakeholder_ref: Optional[Any] = field(default=None, repr=False)
    more_than: Optional[tuple] = None
    benefits: Optional[str] = None
    harms: Optional[str] = None

    def __repr__(self):
        return f"<ValueWeigthing({self.name})>"

from pathlib import Path

@dataclass
class CML:
    domains: List[Domain] = field(default_factory=list)
    context_maps: List[ContextMap] = field(default_factory=list)
    contexts: List[Context] = field(default_factory=list)
    use_cases: List[UseCase] = field(default_factory=list)
    user_stories: List[UserStory] = field(default_factory=list)
    stakeholder_sections: List[StakeholderSection] = field(default_factory=list)
    stakeholder_groups: List[StakeholderGroup] = field(default_factory=list)
    stakeholders: List[Stakeholder] = field(default_factory=list)
    value_registers: List[ValueRegister] = field(default_factory=list)
    traits: List[Trait] = field(default_factory=list)
    tactic_applications: List[TacticDDDApplication] = field(default_factory=list)
    service_cutter: Optional[Any] = None
    parse_results: Optional['ParseResult'] = field(default=None, repr=False)

    def get_domain(self, domain_name: str) -> Optional[Domain]:
        return next((d for d in self.domains if d.name == domain_name), None)

    def get_context_map(self, map_name: str) -> Optional[ContextMap]:
        return next((cm for cm in self.context_maps if cm.name == map_name), None)

    def get_context(self, context_name: str) -> Optional[Context]:
        return next((c for c in self.contexts if c.name == context_name), None)

    def get_aggregate(self, aggregate_name: str, *, context_name: Optional[str] = None) -> Optional[Aggregate]:
        contexts = self.contexts
        if context_name:
            contexts = [c for c in contexts if c.name == context_name]
        for ctx in contexts:
            agg = ctx.get_aggregate(aggregate_name)
            if agg:
                return agg
        return None

    def get_entity(
        self,
        entity_name: str,
        *,
        context_name: Optional[str] = None,
        aggregate_name: Optional[str] = None,
    ) -> Optional[Entity]:
        contexts = self.contexts
        if context_name:
            contexts = [c for c in contexts if c.name == context_name]
        for ctx in contexts:
            aggregates = ctx.aggregates
            if aggregate_name:
                aggregates = [a for a in aggregates if a.name == aggregate_name]
            for agg in aggregates:
                ent = agg.get_entity(entity_name)
                if ent:
                    return ent
        return None

    def get_subdomain(self, subdomain_name: str, *, domain_name: Optional[str] = None) -> Optional[Subdomain]:
        domains = self.domains
        if domain_name:
            domains = [d for d in domains if d.name == domain_name]
        for domain in domains:
            sd = domain.get_subdomain(subdomain_name)
            if sd:
                return sd
        return None

    def get_use_case(self, use_case_name: str) -> Optional[UseCase]:
        return next((uc for uc in self.use_cases if uc.name == use_case_name), None)

    def __repr__(self):
        filename = self.parse_results.filename if self.parse_results else "unknown"
        
        cm_names = ", ".join(cm.name for cm in self.context_maps)
        d_names = ", ".join(d.name for d in self.domains)
        uc_names = ", ".join(uc.name for uc in self.use_cases)
        
        return (f"<CML file={filename} "
                f"context_maps=[{cm_names}] "
                f"domains=[{d_names}] "
                f"use_cases=[{uc_names}]>")
