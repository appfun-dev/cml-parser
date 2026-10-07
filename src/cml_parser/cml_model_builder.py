from typing import List, Optional, Any, Dict, Set
import re
from antlr4 import *
from .antlr.CMLLexer import CMLLexer
from .antlr.CMLParser import CMLParser
from .antlr.CMLVisitor import CMLVisitor
from .cml_objects import (
    CML,
    Domain,
    Subdomain,
    SubdomainType,
    ContextMap,
    Context,
    Relationship,
    RelationshipType,
    UseCase,
    Entity,
    ValueObject,
    DomainEvent,
    BasicType,
    Enum,
    Aggregate,
    Service,
    Resource,
    Consumer,
    Repository,
    Attribute,
    Association,
    Operation,
    Attribute,
    Operation,
    Parameter,
    UserStory,
    Stakeholder,
    StakeholderGroup,
    StakeholderSection,
    ValueRegister,
    ValueCluster,
    Value,
    ValueElicitation,
    ValueConsequence,
    ValueAction,
    ValueEpic,
    ValueNarrative,
    ValueWeigthing,
    Application,
    Flow,
    FlowStep,
    Command,
    Coordination,
    CoordinationStepRef,
    CommandEvent,
    DataTransferObject,
    Module,
    TacticDDDApplication,
    Trait
)
from .service_cutter_objects import (
    ServiceCutterConfig,
    SCAggregate,
    SCSecurityAccessGroup,
    SCEntity,
    SCPredefinedService,
    SCSeparatedSecurityZone,
    SCSharedOwnerGroup,
    SCCompatibilities,
    SCUseCase,
    SCCharacteristic,
)

class CMLModelBuilder(CMLVisitor):
    _TAG_RE = re.compile(r"(?:^|(?<=\s))@([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*([^\s]+)", re.MULTILINE)

    def __init__(self, filename: str = None, token_stream: Optional[CommonTokenStream] = None):
        self.filename = filename
        self.token_stream = token_stream
        self._comment_segments = None  # List[(start_line, end_line, text)]
        self._code_lines = None  # Set[int] of lines containing non-comment tokens
        self.cml = CML()
        self.context_map_obj_map = {} # Name -> Context
        self.subdomain_map = {} # Name -> Subdomain
        self.domain_map = {}  # Name -> Domain

        # Import statements collected during parsing
        self.imports = []  # List of import paths (strings)

        # Deferred linking
        self.deferred_context_map_links = [] # (ContextMap, [names])
        self.deferred_context_links = [] # (Context, [implements_names])
        self.deferred_subdomain_supports = [] # (Subdomain, [requirement_names])
        self.trait_map = {}  # name -> Trait
        self.service_cutter = ServiceCutterConfig()
        
        self.current_domain = None
        self.current_subdomain = None
        self.current_context = None
        self.current_aggregate = None
        self.current_entity = None
        self.current_value_object = None
        self.current_domain_event = None
        self.current_resource = None
        self.current_consumer = None
        self.current_tactic_application = None
        self.current_module = None
        self.current_application = None
        self.current_stakeholder_group = None
        self.current_stakeholder_section = None
        self.current_value_register = None
        self.current_value_cluster = None
        
        self._init_attribute_handlers()

    @staticmethod
    def _strip_quotes(text: str) -> str:
        return text.strip('"').strip("'")
        
    def _init_attribute_handlers(self):
        self.attribute_handlers = {
            # Boolean flags
            "required": ("required", "bool"),
            "unique": ("unique", "bool"),
            "index": ("index", "bool"),
            "changeable": ("changeable", "bool"),
            "cache": ("cache", "bool"),
            "inverse": ("inverse", "bool"),
            "transient": ("transient", "bool"),
            
            # Boolean flags with optional message
            "notEmpty": ("not_empty", "bool_msg", "not_empty_message"),
            "notBlank": ("not_blank", "bool_msg", "not_blank_message"),
            "nullable": ("nullable", "bool_msg", "nullable_message"),
            "email": ("email", "bool_msg", "email_message"),
            "future": ("future", "bool_msg", "future_message"),
            "past": ("past", "bool_msg", "past_message"),
            "valid": ("valid", "bool_msg", "valid_message"),
            
            # String flags
            "pattern": ("pattern", "str"),
            "size": ("size", "str"),
            "min": ("min", "str"),
            "max": ("max", "str"),
            "decimalMax": ("decimal_max", "str"),
            "decimalMin": ("decimal_min", "str"),
            "digits": ("digits", "str"),
            "length": ("length", "str"),
            "range": ("range", "str"),
            "scriptAssert": ("script_assert", "str"),
            "url": ("url", "str"),
            "hint": ("hint", "str"),
            "creditCardNumber": ("credit_card", "str"),
            "assertTrue": ("assert_true", "str"),
            "assertFalse": ("assert_false", "str"),
            "cascade": ("cascade", "str"),
            "fetch": ("fetch", "str"),
            "databaseColumn": ("database_column", "str"),
            "databaseType": ("database_type", "str"),
            "databaseJoinTable": ("database_join_table", "str"),
            "databaseJoinColumn": ("database_join_column", "str"),
            "orderColumn": ("order_column", "str"),
            "validate": ("validate", "str"),
            "orderby": ("order_by", "str"),
        }

    def _apply_attribute_option(self, attr: Attribute, opt: CMLParser.AttributeOptionContext) -> None:
        # opposite is its own sub-rule now (supports `opposite = "x"`, `opposite x`, and `<-> x`)
        if opt.oppositeHolder():
            opposite_holder = opt.oppositeHolder()
            if opposite_holder.STRING():
                attr.opposite = self._strip_quotes(opposite_holder.STRING().getText())
            elif opposite_holder.name():
                attr.opposite = opposite_holder.name().getText()
            return

        key = opt.attributeOptionKey().getText() if opt.attributeOptionKey() else opt.getText()
        val = self._strip_quotes(opt.STRING().getText()) if opt.STRING() else None
        negated = opt.notPrefix() is not None
        
        handler = self.attribute_handlers.get(key)
        if not handler:
            return

        target_attr, kind, *extra = handler
        
        if kind == "bool":
            setattr(attr, target_attr, not negated)
        elif kind == "bool_msg":
            setattr(attr, target_attr, not negated)
            if val and extra:
                setattr(attr, extra[0], val)
        elif kind == "str":
            setattr(attr, target_attr, val)


    def _merge_traits(self, target_obj: Any) -> None:
        if not hasattr(target_obj, "traits") or not target_obj.traits:
            return

        for trait_name in target_obj.traits:
            trait_obj = self.trait_map.get(trait_name)
            if not trait_obj:
                continue

            # Merge attributes
            if hasattr(target_obj, "attributes"):
                existing_attr_names = {a.name for a in target_obj.attributes}
                for attr in trait_obj.attributes:
                    if attr.name not in existing_attr_names:
                        target_obj.attributes.append(attr)

            # Merge operations
            if hasattr(target_obj, "operations"):
                existing_op_names = {o.name for o in target_obj.operations}
                for op in trait_obj.operations:
                    if op.name not in existing_op_names:
                        target_obj.operations.append(op)

            # Merge associations
            if hasattr(target_obj, "associations"):
                existing_assoc_keys = {
                    (a.target, a.is_reference, a.description) 
                    for a in getattr(target_obj, "associations", [])
                }
                for assoc in getattr(trait_obj, "associations", []) or []:
                    key = (assoc.target, assoc.is_reference, assoc.description)
                    if key in existing_assoc_keys:
                        continue
                    
                    # Create new association object to avoid shared mutable state issues
                    new_assoc = Association(
                        target=assoc.target, 
                        is_reference=assoc.is_reference, 
                        description=assoc.description
                    )
                    target_obj.associations.append(new_assoc)
                    existing_assoc_keys.add(key)

    # --- Comment and tag extraction ---

    @staticmethod
    def _clean_comment_text(text: str) -> str:
        if text.startswith("//"):
            return text[2:].strip()
        if text.startswith("/*"):
            body = text[2:-2] if text.endswith("*/") else text[2:]
            lines = [l.strip().lstrip("*").strip() for l in body.splitlines()]
            return "\n".join(l for l in lines if l)
        return text.strip()

    def _ensure_comment_index(self) -> None:
        if self._comment_segments is not None:
            return
        self._comment_segments = []
        self._code_lines = set()
        if self.token_stream is None:
            return
        for token in self.token_stream.tokens:
            if token.type == Token.EOF:
                continue
            if token.type in (CMLLexer.COMMENT, CMLLexer.BLOCK_COMMENT):
                start = token.line
                end = start + token.text.count("\n")
                self._comment_segments.append((start, end, self._clean_comment_text(token.text)))
            else:
                self._code_lines.add(token.line)
        self._comment_segments.sort(key=lambda s: s[0])

    def _leading_comment(self, ctx) -> Optional[str]:
        """Contiguous comment paragraph immediately above the block's first line."""
        if ctx.start is None:
            return None
        parts = []
        cursor = ctx.start.line
        while True:
            seg = next((s for s in self._comment_segments if s[1] == cursor - 1), None)
            if seg is None or seg[0] in self._code_lines:
                break
            parts.append(seg[2])
            cursor = seg[0]
        parts.reverse()
        text = "\n".join(p for p in parts if p)
        return text or None

    def _inner_comment(self, ctx) -> Optional[str]:
        """First contiguous comment paragraph inside the block, right after '{'."""
        if ctx.start is None or self.token_stream is None:
            return None
        tokens = self.token_stream.tokens
        stop_index = ctx.stop.tokenIndex if ctx.stop is not None else len(tokens) - 1
        brace_line = None
        for i in range(ctx.start.tokenIndex, stop_index + 1):
            if tokens[i].text == "{":
                brace_line = tokens[i].line
                break
        if brace_line is None:
            return None
        parts = []
        cursor = brace_line + 1
        while True:
            seg = next((s for s in self._comment_segments if s[0] == cursor), None)
            if seg is None or seg[0] in self._code_lines:
                break
            parts.append(seg[2])
            cursor = seg[1] + 1
        text = "\n".join(p for p in parts if p)
        return text or None

    @classmethod
    def _extract_tags(cls, *texts: Optional[str]) -> Dict[str, List[str]]:
        """Extract @key:value tags from comment texts."""
        tags: Dict[str, List[str]] = {}
        for text in texts:
            if not text:
                continue
            for match in cls._TAG_RE.finditer(text):
                tags.setdefault(match.group(1), []).append(match.group(2))
        return tags

    def _attach_comments(self, obj: Any, ctx) -> None:
        """Attach leading/inner comments and @key:value tags to a block object."""
        if self.token_stream is None:
            return
        if not hasattr(obj, "_doc_tags"):
            return
        self._ensure_comment_index()
        leading = self._leading_comment(ctx)
        inner = self._inner_comment(ctx)
        obj.leading_comment = leading
        obj.inner_comment = inner
        tags = self._extract_tags(leading, inner)
        if tags:
            obj._doc_tags = tags

    def visitImports(self, ctx: CMLParser.ImportsContext):
        """Collect import statement paths for later resolution."""
        import_path = self._strip_quotes(ctx.STRING().getText())
        self.imports.append(import_path)
        return None

    def visitDefinitions(self, ctx: CMLParser.DefinitionsContext):
        try:
            self.visitChildren(ctx)
        except Exception as e:
            raise e

        # Post-processing: Link contexts and subdomains
        self._link_references()
        # Attach service cutter config if any content was collected
        if (
            self.service_cutter.aggregates
            or self.service_cutter.security_access_groups
            or self.service_cutter.entities
            or self.service_cutter.predefined_services
            or self.service_cutter.separated_security_zones
            or self.service_cutter.shared_owner_groups
            or self.service_cutter.compatibilities
            or self.service_cutter.use_cases
            or self.service_cutter.characteristics
        ):
            self.cml.service_cutter = self.service_cutter
        
        return self.cml

    def _link_references(self):
        # Link ContextMap contains
        for cm, ctx_names in self.deferred_context_map_links:
            for name in ctx_names:
                ctx = self.context_map_obj_map.get(name)
                if ctx:
                    if ctx not in cm.contexts:
                        cm.contexts.append(ctx)
                    ctx.context_map = cm
        
        # Link BoundedContext implements
        for ctx, subdomain_names in self.deferred_context_links:
            for name in subdomain_names:
                sd = self.subdomain_map.get(name)
                if sd:
                    ctx.implements.append(sd)
                    sd.implementations.append(ctx)
                    continue
                dom = self.domain_map.get(name)
                if dom:
                    ctx.implements.append(dom)
                    dom.implementations.append(ctx)

        # Link Subdomain supports -> use cases or user stories
        for sd, req_names in self.deferred_subdomain_supports:
            for name in req_names:
                req = next((u for u in self.cml.use_cases if u.name == name), None)
                if not req:
                    req = next((s for s in self.cml.user_stories if s.name == name), None)
                if not req:
                    req = UseCase(name=name)
                    self.cml.use_cases.append(req)
                sd.supported_requirements.append(req)

        # Link Relationship exposedAggregates -> Aggregate objects
        aggregate_index: Dict[str, List[Aggregate]] = {}
        for ctx in self.cml.contexts:
            for agg in getattr(ctx, "aggregates", []):
                aggregate_index.setdefault(agg.name, []).append(agg)
            for mod in getattr(ctx, "modules", []):
                for agg in getattr(mod, "aggregates", []):
                    aggregate_index.setdefault(agg.name, []).append(agg)

        def _find_aggregate_in_context(context: Context, name: str) -> Optional[Aggregate]:
            agg = context.get_aggregate(name)
            if agg:
                return agg
            for mod in context.modules:
                for mod_agg in mod.aggregates:
                    if mod_agg.name == name:
                        return mod_agg
            return None

        for cm in self.cml.context_maps:
            for rel in cm.relationships:
                if not rel.exposed_aggregates:
                    continue
                resolved: List[Aggregate] = []
                candidate_contexts: List[Context] = []
                if rel.upstream:
                    candidate_contexts.append(rel.upstream)
                if rel.downstream and rel.downstream not in candidate_contexts:
                    candidate_contexts.append(rel.downstream)

                for name in rel.exposed_aggregates:
                    agg_obj = None
                    for candidate in candidate_contexts:
                        agg_obj = _find_aggregate_in_context(candidate, name)
                        if agg_obj:
                            break
                    if not agg_obj:
                        candidates = aggregate_index.get(name, [])
                        agg_obj = candidates[0] if candidates else None
                    if agg_obj and agg_obj not in resolved:
                        resolved.append(agg_obj)
                rel.exposed_aggregate_refs = resolved

        # Link Coordination step refs to services/operations (best-effort)
        for ctx in self.cml.contexts:
            apps = []
            if ctx.application:
                apps.append(ctx.application)
            for mod in ctx.modules:
                if mod.application:
                    apps.append(mod.application)

            for app in apps:
                for coord in app.coordinations:
                    for step_ref in coord.step_refs:
                        if not step_ref.bounded_context_ref:
                            step_ref.bounded_context_ref = self._get_or_create_context(step_ref.bounded_context)
                        bc = step_ref.bounded_context_ref
                        if not bc:
                            continue
                        svc = bc.get_service(step_ref.service)
                        if not svc:
                            continue
                        step_ref.service_ref = svc
                        op = svc.get_operation(step_ref.operation)
                        if op:
                            step_ref.operation_ref = op

        # Link FlowStep references (best-effort)
        for ctx in self.cml.contexts:
            apps: List[Application] = []
            if ctx.application:
                apps.append(ctx.application)
            for mod in ctx.modules:
                if mod.application:
                    apps.append(mod.application)

            # Build indexes for this bounded context
            def _find_aggregate(name: str) -> Optional[Aggregate]:
                agg = ctx.get_aggregate(name)
                if agg:
                    return agg
                for mod in ctx.modules:
                    for mod_agg in mod.aggregates:
                        if mod_agg.name == name:
                            return mod_agg
                return None

            base_domain_event_index: Dict[str, DomainEvent] = {}
            base_command_event_index: Dict[str, CommandEvent] = {}
            base_service_operation_index: Dict[str, Operation] = {}

            for agg in getattr(ctx, "aggregates", []):
                for de in getattr(agg, "domain_events", []):
                    base_domain_event_index.setdefault(de.name, de)
                for ce in getattr(agg, "command_events", []):
                    base_command_event_index.setdefault(ce.name, ce)

            for mod in getattr(ctx, "modules", []):
                for mod_agg in getattr(mod, "aggregates", []):
                    for de in getattr(mod_agg, "domain_events", []):
                        base_domain_event_index.setdefault(de.name, de)
                    for ce in getattr(mod_agg, "command_events", []):
                        base_command_event_index.setdefault(ce.name, ce)

                for obj in getattr(mod, "domain_objects", []):
                    if isinstance(obj, DomainEvent):
                        base_domain_event_index.setdefault(obj.name, obj)
                    elif isinstance(obj, CommandEvent):
                        base_command_event_index.setdefault(obj.name, obj)

            all_services: List[Service] = []
            all_services.extend(getattr(ctx, "services", []))
            for agg in getattr(ctx, "aggregates", []):
                all_services.extend(getattr(agg, "services", []))
            for mod in getattr(ctx, "modules", []):
                all_services.extend(getattr(mod, "services", []))

            for svc in all_services:
                for op in getattr(svc, "operations", []):
                    base_service_operation_index.setdefault(op.name, op)

            for app in apps:
                domain_event_index: Dict[str, DomainEvent] = dict(base_domain_event_index)
                command_event_index: Dict[str, CommandEvent] = dict(base_command_event_index)
                service_operation_index: Dict[str, Operation] = dict(base_service_operation_index)

                for de in getattr(app, "domain_events", []):
                    domain_event_index[de.name] = de

                for ce in getattr(app, "command_events", []):
                    command_event_index[ce.name] = ce

                # Treat `Command Foo` declarations as shorthand CommandEvent definitions (Xtext-like)
                for cmd_decl in getattr(app, "commands", []):
                    if any(existing.name == cmd_decl.name for existing in getattr(app, "command_events", [])):
                        continue
                    placeholder = CommandEvent(name=cmd_decl.name)
                    app.command_events.append(placeholder)
                    command_event_index[placeholder.name] = placeholder

                for svc in getattr(app, "services", []):
                    for op in getattr(svc, "operations", []):
                        service_operation_index[op.name] = op

                for flow in getattr(app, "flows", []):
                    for step in getattr(flow, "steps", []):
                        if step.delegate:
                            step.delegate_ref = _find_aggregate(step.delegate)

                        if step.emits:
                            step.emit_refs = [
                                domain_event_index[name]
                                for name in step.emits
                                if name in domain_event_index
                            ]

                        if step.type == "command":
                            step.command_ref = command_event_index.get(step.name)
                        elif step.type == "operation":
                            step.operation_ref = service_operation_index.get(step.name)
                        elif step.type == "event":
                            if step.triggers:
                                step.trigger_refs = [
                                    domain_event_index[name]
                                    for name in step.triggers
                                    if name in domain_event_index
                                ]

                            # Link invocations (propagate missing kinds like Xtext)
                            step.invocation_command_refs = []
                            step.invocation_operation_refs = []
                            last_kind: Optional[str] = None
                            for kind, name in zip(step.invocation_kinds, step.invocations):
                                effective_kind = kind or last_kind
                                if kind:
                                    last_kind = kind

                                if effective_kind == "command":
                                    step.invocation_command_refs.append(command_event_index.get(name))
                                    step.invocation_operation_refs.append(None)
                                elif effective_kind == "operation":
                                    step.invocation_command_refs.append(None)
                                    step.invocation_operation_refs.append(service_operation_index.get(name))
                                else:
                                    step.invocation_command_refs.append(None)
                                    step.invocation_operation_refs.append(None)

        # Link Context.realizes/refines and other Context references
        for ctx in list(self.cml.contexts):
            if getattr(ctx, "realizes", None):
                ctx.realizes_refs = [self._get_or_create_context(n) for n in ctx.realizes]
            if getattr(ctx, "refines", None):
                ctx.refines_ref = self._get_or_create_context(ctx.refines)

            for agg in getattr(ctx, "aggregates", []):
                if getattr(agg, "owner", None):
                    agg.owner_ref = self._get_or_create_context(agg.owner)

            for mod in getattr(ctx, "modules", []):
                for agg in getattr(mod, "aggregates", []):
                    if getattr(agg, "owner", None):
                        agg.owner_ref = self._get_or_create_context(agg.owner)

        for reg in getattr(self.cml, "value_registers", []):
            if getattr(reg, "context", None):
                reg.context_ref = self._get_or_create_context(reg.context)

        for section in getattr(self.cml, "stakeholder_sections", []):
            if getattr(section, "contexts", None):
                section.contexts_refs = [self._get_or_create_context(n) for n in section.contexts]

        # Link tactical cross-references (best-effort)
        # - extends/belongsTo -> domain object refs
        # - Association targets -> domain object refs
        from collections import defaultdict

        all_named_objects: List[Any] = []
        obj_to_ctx_name: Dict[int, str] = {}
        global_buckets: Dict[str, List[Any]] = defaultdict(list)
        ctx_buckets: Dict[str, Dict[str, List[Any]]] = defaultdict(lambda: defaultdict(list))
        all_operations: List[Operation] = []
        operation_to_ctx_name: Dict[int, str] = {}

        service_global_buckets: Dict[str, List[Service]] = defaultdict(list)
        repo_global_buckets: Dict[str, List[Repository]] = defaultdict(list)
        ctx_service_buckets: Dict[str, Dict[str, List[Service]]] = defaultdict(lambda: defaultdict(list))
        ctx_repo_buckets: Dict[str, Dict[str, List[Repository]]] = defaultdict(lambda: defaultdict(list))
        holder_ops_unique: Dict[int, Dict[str, Operation]] = {}

        def add_named(obj: Any, *, ctx_name: Optional[str]) -> None:
            n = getattr(obj, "name", None)
            if not n or not isinstance(n, str):
                return
            all_named_objects.append(obj)
            global_buckets[n].append(obj)
            if ctx_name:
                obj_to_ctx_name[id(obj)] = ctx_name
                ctx_buckets[ctx_name][n].append(obj)

        def add_holder_ops(holder: Any, *, ctx_name: Optional[str]) -> None:
            ops = getattr(holder, "operations", []) or []
            if ctx_name:
                for op in ops:
                    operation_to_ctx_name[id(op)] = ctx_name
                    all_operations.append(op)
            bucket: Dict[str, List[Operation]] = defaultdict(list)
            for op in ops:
                if getattr(op, "name", None):
                    bucket[op.name].append(op)
            holder_ops_unique[id(holder)] = {n: olist[0] for n, olist in bucket.items() if len(olist) == 1}

        def add_service(svc: Service, *, ctx_name: Optional[str]) -> None:
            if not getattr(svc, "name", None):
                return
            service_global_buckets[svc.name].append(svc)
            if ctx_name:
                ctx_service_buckets[ctx_name][svc.name].append(svc)
            add_holder_ops(svc, ctx_name=ctx_name)

        def add_repository(repo: Repository, *, ctx_name: Optional[str]) -> None:
            if not getattr(repo, "name", None):
                return
            repo_global_buckets[repo.name].append(repo)
            if ctx_name:
                ctx_repo_buckets[ctx_name][repo.name].append(repo)
            add_holder_ops(repo, ctx_name=ctx_name)

        def collect_aggregate_objects(agg: Any, *, ctx_name: Optional[str]) -> None:
            for obj in getattr(agg, "entities", []):
                add_named(obj, ctx_name=ctx_name)
            for obj in getattr(agg, "value_objects", []):
                add_named(obj, ctx_name=ctx_name)
            for obj in getattr(agg, "domain_events", []):
                add_named(obj, ctx_name=ctx_name)
            for obj in getattr(agg, "command_events", []):
                add_named(obj, ctx_name=ctx_name)
            for obj in getattr(agg, "data_transfer_objects", []):
                add_named(obj, ctx_name=ctx_name)
            for obj in getattr(agg, "basic_types", []):
                add_named(obj, ctx_name=ctx_name)
            for obj in getattr(agg, "enums", []):
                add_named(obj, ctx_name=ctx_name)
            for svc in getattr(agg, "services", []):
                add_service(svc, ctx_name=ctx_name)
            for repo in getattr(agg, "repositories", []):
                add_repository(repo, ctx_name=ctx_name)

        for ctx in list(getattr(self.cml, "contexts", [])):
            ctx_name = getattr(ctx, "name", None)

            if getattr(ctx, "application", None):
                app = ctx.application
                for obj in getattr(app, "domain_events", []):
                    add_named(obj, ctx_name=ctx_name)
                for obj in getattr(app, "command_events", []):
                    add_named(obj, ctx_name=ctx_name)
                for svc in getattr(app, "services", []):
                    add_service(svc, ctx_name=ctx_name)

            for svc in getattr(ctx, "services", []):
                add_service(svc, ctx_name=ctx_name)

            for agg in getattr(ctx, "aggregates", []):
                collect_aggregate_objects(agg, ctx_name=ctx_name)

            for mod in getattr(ctx, "modules", []):
                for obj in getattr(mod, "domain_objects", []):
                    add_named(obj, ctx_name=ctx_name)
                for svc in getattr(mod, "services", []):
                    add_service(svc, ctx_name=ctx_name)
                for agg in getattr(mod, "aggregates", []):
                    collect_aggregate_objects(agg, ctx_name=ctx_name)

        for dom in getattr(self.cml, "domains", []):
            for sd in getattr(dom, "subdomains", []):
                for ent in getattr(sd, "entities", []):
                    add_named(ent, ctx_name=None)

        for app in getattr(self.cml, "tactic_applications", []):
            for obj in getattr(app, "domain_objects", []):
                add_named(obj, ctx_name=None)
            for svc in getattr(app, "services", []):
                add_service(svc, ctx_name=None)

        global_unique = {n: objs[0] for n, objs in global_buckets.items() if len(objs) == 1}
        ctx_unique: Dict[str, Dict[str, Any]] = {}
        for ctx_name, buckets in ctx_buckets.items():
            ctx_unique[ctx_name] = {n: objs[0] for n, objs in buckets.items() if len(objs) == 1}

        ctx_service_unique: Dict[str, Dict[str, Service]] = {}
        ctx_repo_unique: Dict[str, Dict[str, Repository]] = {}
        for ctx_name, buckets in ctx_service_buckets.items():
            ctx_service_unique[ctx_name] = {n: objs[0] for n, objs in buckets.items() if len(objs) == 1}
        for ctx_name, buckets in ctx_repo_buckets.items():
            ctx_repo_unique[ctx_name] = {n: objs[0] for n, objs in buckets.items() if len(objs) == 1}
        service_global_unique = {n: objs[0] for n, objs in service_global_buckets.items() if len(objs) == 1}
        repo_global_unique = {n: objs[0] for n, objs in repo_global_buckets.items() if len(objs) == 1}

        def resolve_domain_object(name: str, *, ctx_name: Optional[str]) -> Optional[Any]:
            if not name:
                return None
            n = name.lstrip("@")
            if ctx_name and n in ctx_unique.get(ctx_name, {}):
                return ctx_unique[ctx_name][n]
            if n in global_unique:
                return global_unique[n]
            if "." in n:
                last = n.split(".")[-1]
                if ctx_name and last in ctx_unique.get(ctx_name, {}):
                    return ctx_unique[ctx_name][last]
                return global_unique.get(last)
            return None

        def resolve_holder(name: str, *, ctx_name: Optional[str]) -> Optional[Any]:
            if not name:
                return None
            n = name.lstrip("@")
            if "." in n:
                n = n.split(".")[-1]

            if ctx_name:
                repo = ctx_repo_unique.get(ctx_name, {}).get(n)
                if repo:
                    return repo
                svc = ctx_service_unique.get(ctx_name, {}).get(n)
                if svc:
                    return svc

            repo = repo_global_unique.get(n)
            if repo:
                return repo
            return service_global_unique.get(n)

        seen: Set[int] = set()
        for obj in all_named_objects:
            oid = id(obj)
            if oid in seen:
                continue
            seen.add(oid)

            ctx_name = obj_to_ctx_name.get(oid)

            if hasattr(obj, "operations"):
                for op in getattr(obj, "operations", []) or []:
                    if ctx_name:
                        operation_to_ctx_name[id(op)] = ctx_name
                    all_operations.append(op)

            # belongsTo
            if hasattr(obj, "belongs_to") and getattr(obj, "belongs_to", None):
                target = resolve_domain_object(getattr(obj, "belongs_to"), ctx_name=ctx_name)
                if target is not None and hasattr(obj, "belongs_to_ref"):
                    obj.belongs_to_ref = target

            # extends
            if hasattr(obj, "extends") and getattr(obj, "extends", None):
                target = resolve_domain_object(getattr(obj, "extends"), ctx_name=ctx_name)
                if target is not None and isinstance(target, obj.__class__) and hasattr(obj, "extends_ref"):
                    obj.extends_ref = target

            # association targets
            if hasattr(obj, "associations"):
                for assoc in getattr(obj, "associations", []) or []:
                    if not getattr(assoc, "target", None):
                        continue
                    assoc.target_ref = resolve_domain_object(assoc.target, ctx_name=ctx_name)

        # Link Consumer.unmarshall_to -> DomainObject refs (best-effort)
        for ctx in getattr(self.cml, "contexts", []) or []:
            ctx_name = getattr(ctx, "name", None)

            for consumer in getattr(ctx, "consumers", []) or []:
                if getattr(consumer, "unmarshall_to", None):
                    consumer.unmarshall_to_ref = resolve_domain_object(consumer.unmarshall_to, ctx_name=ctx_name)

            for agg in getattr(ctx, "aggregates", []) or []:
                for consumer in getattr(agg, "consumers", []) or []:
                    if getattr(consumer, "unmarshall_to", None):
                        consumer.unmarshall_to_ref = resolve_domain_object(consumer.unmarshall_to, ctx_name=ctx_name)

            for mod in getattr(ctx, "modules", []) or []:
                for consumer in getattr(mod, "consumers", []) or []:
                    if getattr(consumer, "unmarshall_to", None):
                        consumer.unmarshall_to_ref = resolve_domain_object(consumer.unmarshall_to, ctx_name=ctx_name)

                for agg in getattr(mod, "aggregates", []) or []:
                    for consumer in getattr(agg, "consumers", []) or []:
                        if getattr(consumer, "unmarshall_to", None):
                            consumer.unmarshall_to_ref = resolve_domain_object(consumer.unmarshall_to, ctx_name=ctx_name)

        for app in getattr(self.cml, "tactic_applications", []) or []:
            for consumer in getattr(app, "consumers", []) or []:
                if getattr(consumer, "unmarshall_to", None):
                    consumer.unmarshall_to_ref = resolve_domain_object(consumer.unmarshall_to, ctx_name=None)

        seen_ops: Set[int] = set()
        for op in all_operations:
            oid = id(op)
            if oid in seen_ops:
                continue
            seen_ops.add(oid)

            ctx_name = operation_to_ctx_name.get(oid)

            if getattr(op, "publishes_event_type", None):
                target = resolve_domain_object(op.publishes_event_type, ctx_name=ctx_name)
                if isinstance(target, (DomainEvent, CommandEvent)):
                    op.publishes_event_type_ref = target

            if getattr(op, "subscribes_event_type", None):
                target = resolve_domain_object(op.subscribes_event_type, ctx_name=ctx_name)
                if isinstance(target, (DomainEvent, CommandEvent)):
                    op.subscribes_event_type_ref = target

            if getattr(op, "delegate_target", None):
                raw_target = op.delegate_target.lstrip("@")
                parts = [p for p in raw_target.split(".") if p]
                if not parts:
                    continue
                if len(parts) == 1:
                    holder_name = parts[0]
                    op_name = None
                else:
                    op_name = parts[-1]
                    holder_name = parts[-2]

                holder = resolve_holder(holder_name, ctx_name=ctx_name)
                if holder is None:
                    continue

                op.delegate_holder_ref = holder
                if op_name:
                    op.delegate_operation_ref = holder_ops_unique.get(id(holder), {}).get(op_name)

        # Link ValueRegister stakeholder cross-references (best-effort)
        abstract_stakeholder_buckets: Dict[str, List[Any]] = defaultdict(list)
        for s in getattr(self.cml, "stakeholders", []):
            if getattr(s, "name", None):
                abstract_stakeholder_buckets[s.name].append(s)
        for g in getattr(self.cml, "stakeholder_groups", []):
            if getattr(g, "name", None):
                abstract_stakeholder_buckets[g.name].append(g)
            for s in getattr(g, "stakeholders", []):
                if getattr(s, "name", None):
                    abstract_stakeholder_buckets[s.name].append(s)

        abstract_stakeholder_unique = {
            n: objs[0] for n, objs in abstract_stakeholder_buckets.items() if len(objs) == 1
        }

        for reg in getattr(self.cml, "value_registers", []):
            for cluster in getattr(reg, "clusters", []):
                for elic in getattr(cluster, "elicitations", []):
                    elic.stakeholder_ref = abstract_stakeholder_unique.get(elic.stakeholder)
                for val in getattr(cluster, "values", []):
                    for elic in getattr(val, "elicitations", []):
                        elic.stakeholder_ref = abstract_stakeholder_unique.get(elic.stakeholder)

            for val in getattr(reg, "values", []):
                for elic in getattr(val, "elicitations", []):
                    elic.stakeholder_ref = abstract_stakeholder_unique.get(elic.stakeholder)

            for epic in getattr(reg, "epics", []):
                if getattr(epic, "stakeholder", None):
                    epic.stakeholder_ref = abstract_stakeholder_unique.get(epic.stakeholder)

            for vw in getattr(reg, "weightings", []):
                if getattr(vw, "stakeholder", None):
                    vw.stakeholder_ref = abstract_stakeholder_unique.get(vw.stakeholder)

    def visitContextMap(self, ctx: CMLParser.ContextMapContext):
        name = ctx.name().getText() if ctx.name() else "ContextMap"
        cm = ContextMap(name=name, type="UNDEFINED", state="UNDEFINED")
        self._attach_comments(cm, ctx)
        
        # Process settings
        contains_list = []
        for setting in ctx.contextMapSetting():
            if setting.contextMapType():
                cm.type = setting.contextMapType().getText()
            elif setting.contextMapState():
                cm.state = setting.contextMapState().getText()
            elif setting.idList():
                # contains
                names = [id_node.getText() for id_node in setting.idList().name()]
                contains_list.extend(names)
            else:  # pragma: no cover
                pass
                
        if contains_list:
            self.deferred_context_map_links.append((cm, contains_list))
        
        # Process relationships
        for rel_ctx in ctx.relationship():
            rel = self.visitRelationship(rel_ctx)
            if rel:  # pragma: no branch
                cm.relationships.append(rel)
                # Add contexts to map if not present
                if rel.left and rel.left not in cm.contexts:
                    cm.contexts.append(rel.left)
                if rel.right and rel.right not in cm.contexts:
                    cm.contexts.append(rel.right)
        
        self.cml.context_maps.append(cm)
        return cm

    def visitRelationship(self, ctx: CMLParser.RelationshipContext):
        left_endpoint = ctx.relationshipEndpoint()
        right_endpoint = ctx.relationshipEndpointRight()
        
        left_name = left_endpoint.name().getText()
        right_name = right_endpoint.name().getText()
        
        left_ctx = self._get_or_create_context(left_name)
        right_ctx = self._get_or_create_context(right_name)
        
        connection = ctx.relationshipConnection()
        connection_text = "Unknown"
        rel_type = "Unknown"
        if connection.relationshipArrow():
            connection_text = connection.relationshipArrow().getText()
        elif connection.relationshipKeyword():
            connection_text = connection.relationshipKeyword().getText()
            rel_type = connection_text
            
        # Extract roles
        def _endpoint_roles(endpoint) -> List[str]:
            endpoint_roles: List[str] = []
            roles_ctxs = endpoint.relationshipRoles() if hasattr(endpoint, "relationshipRoles") else None
            if roles_ctxs:
                if not isinstance(roles_ctxs, list):
                    roles_ctxs = [roles_ctxs]
                for roles_ctx in roles_ctxs:
                    for role in roles_ctx.relationshipRole():
                        endpoint_roles.append(role.getText())
            return endpoint_roles

        left_roles = _endpoint_roles(left_endpoint)
        right_roles = _endpoint_roles(right_endpoint)
        roles = left_roles + right_roles

        # Infer Xtext-like relationship type from arrow + role markers
        if connection.relationshipArrow():
            if connection_text == "<->":
                rel_type = "Partnership" if "P" in roles else "Shared-Kernel"
            elif connection_text == "->":
                rel_type = "Customer-Supplier" if ("S" in roles or "C" in roles) else "Upstream-Downstream"
            elif connection_text == "<-":
                rel_type = "Customer-Supplier" if ("S" in roles or "C" in roles) else "Downstream-Upstream"

        rel = Relationship(left=left_ctx, right=right_ctx, type=rel_type, roles=roles)
        rel.connection = connection_text if connection_text != "Unknown" else None
        if ctx.ID():
            rel.name = ctx.ID().getText()

        if connection.relationshipArrow():
            if connection_text == "->":
                rel.upstream = left_ctx
                rel.downstream = right_ctx
                rel.upstream_roles = left_roles
                rel.downstream_roles = right_roles
            elif connection_text == "<-":
                rel.upstream = right_ctx
                rel.downstream = left_ctx
                rel.upstream_roles = right_roles
                rel.downstream_roles = left_roles
        elif connection.relationshipKeyword():
            if connection_text in ("Upstream-Downstream", "Supplier-Customer"):
                rel.upstream = left_ctx
                rel.downstream = right_ctx
                rel.upstream_roles = left_roles
                rel.downstream_roles = right_roles
            elif connection_text in ("Downstream-Upstream", "Customer-Supplier"):
                rel.upstream = right_ctx
                rel.downstream = left_ctx
                rel.upstream_roles = right_roles
                rel.downstream_roles = left_roles
        
        # Extract attributes
        if ctx.relationshipAttribute():
            for attr in ctx.relationshipAttribute():
                if 'implementationTechnology' in attr.getText():
                    rel.implementation_technology = attr.STRING().getText().strip('"')
                elif 'downstreamRights' in attr.getText():
                    if attr.downstreamRights():  # pragma: no branch
                        rel.downstream_rights = attr.downstreamRights().getText()
                elif 'exposedAggregates' in attr.getText():
                    if attr.idList():  # pragma: no branch
                        rel.exposed_aggregates = [n.getText() for n in attr.idList().name()]
                        
        return rel

    def _get_or_create_context(self, name: str) -> Context:
        if name in self.context_map_obj_map:
            return self.context_map_obj_map[name]
        
        ctx = Context(name=name)
        self.context_map_obj_map[name] = ctx
        if ctx not in self.cml.contexts:  # pragma: no branch
            self.cml.contexts.append(ctx)
        return ctx

    def visitBoundedContext(self, ctx: CMLParser.BoundedContextContext):
        ctx_names = ctx.name()
        if isinstance(ctx_names, list):
            name = ctx_names[0].getText()
        else:
            name = ctx_names.getText()
        context = self._get_or_create_context(name)
        self._attach_comments(context, ctx)

        implements_list = []
        realizes_list = []
        refines_name = None

        for clause in ctx.boundedContextLinkClause() or []:
            kind = clause.getChild(0).getText()
            if kind == "implements" and clause.idList():
                implements_list.extend([n.getText() for n in clause.idList().name()])
            elif kind == "realizes" and clause.idList():
                realizes_list.extend([n.getText() for n in clause.idList().name()])
            elif kind == "refines" and clause.name():
                refines_name = clause.name().getText()
        
        if implements_list:
            self.deferred_context_links.append((context, implements_list))
        if realizes_list:
            context.realizes = realizes_list
        if refines_name:
            context.refines = refines_name
        
        self.current_context = context
        if ctx.body:
            self.visit(ctx.body)
        self.current_context = None
        
        return context

    def visitTacticDDDApplication(self, ctx: CMLParser.TacticDDDApplicationContext):
        name = ctx.name().getText()
        app = TacticDDDApplication(name=name)
        self._attach_comments(app, ctx)

        if ctx.qualifiedName():
            app.base_package = ctx.qualifiedName().getText()

        prev_app = getattr(self, "current_tactic_application", None)
        self.current_tactic_application = app
        for element in ctx.tacticDDDElement():
            self.visit(element)
        self.current_tactic_application = prev_app

        self.cml.tactic_applications.append(app)
        return app

    def visitDomain(self, ctx: CMLParser.DomainContext):
        name = ctx.name().getText()
        domain = Domain(name=name, vision="")
        self._attach_comments(domain, ctx)
        self.current_domain = domain
        self.domain_map[name] = domain
        
        if ctx.body:
            self.visit(ctx.body)
            
        self.cml.domains.append(domain)
        self.current_domain = None
        return domain

    def visitSubdomain(self, ctx: CMLParser.SubdomainContext):
        name = ctx.name().getText()
        # Type is set via subdomainAttribute inside the body, not directly on subdomain
        sd_type = SubdomainType.UNDEFINED if hasattr(SubdomainType, "UNDEFINED") else SubdomainType.GENERIC

        subdomain = Subdomain(name=name, type=sd_type, vision="", domain=self.current_domain)
        self._attach_comments(subdomain, ctx)
        self.subdomain_map[name] = subdomain

        # Collect supports clauses for deferred linking
        if ctx.idList():
            req_names = [n.getText() for n in ctx.idList().name()]
            if req_names:
                self.deferred_subdomain_supports.append((subdomain, req_names))
        
        if self.current_domain:
            self.current_domain.subdomains.append(subdomain)
        else:  # pragma: no cover
            # Orphan subdomain, logic TBD
            pass
            
        prev_subdomain = getattr(self, 'current_subdomain', None)
        self.current_subdomain = subdomain
        
        if ctx.body:
            self.visit(ctx.body)
            
        self.current_subdomain = prev_subdomain
        return subdomain

    def visitAggregate(self, ctx: CMLParser.AggregateContext):
        name = ctx.name().getText()
        agg = Aggregate(name=name)
        self._attach_comments(agg, ctx)
        
        if self.current_module:
            self.current_module.aggregates.append(agg)
            if self.current_context:
                agg.context = self.current_context
        elif self.current_context:
            agg.context = self.current_context
            self.current_context.aggregates.append(agg)
            
        self.current_aggregate = agg
        if ctx.body:
            self.visit(ctx.body)
        self.current_aggregate = None
        return agg

    def visitAggregateAttribute(self, ctx: CMLParser.AggregateAttributeContext):
        if not self.current_aggregate:
            return None

        agg = self.current_aggregate
        keyword = ctx.getChild(0).getText() if ctx.getChildCount() else ctx.getText()

        if keyword in ("useCases", "userStories", "features", "userRequirements") and ctx.idList():
            names = [n.getText() for n in ctx.idList().name()]
            for n in names:
                if keyword == "useCases":
                    req = next((u for u in self.cml.use_cases if u.name == n), None) or UseCase(name=n)
                    if req not in self.cml.use_cases:
                        self.cml.use_cases.append(req)
                elif keyword == "userStories":
                    req = next((s for s in self.cml.user_stories if s.name == n), None) or UserStory(name=n)
                    if req not in self.cml.user_stories:
                        self.cml.user_stories.append(req)
                else:
                    req = next((u for u in self.cml.use_cases if u.name == n), None)
                    if not req:
                        req = next((s for s in self.cml.user_stories if s.name == n), None)
                    if not req:
                        req = UseCase(name=n)
                        self.cml.use_cases.append(req)
                agg.user_requirements.append(req)
            return None

        if keyword in ("likelihoodForChange", "structuralVolatility") and ctx.volatility():
            agg.likelihood_for_change = ctx.volatility().getText()
        elif keyword == "contentVolatility" and ctx.volatility():
            agg.content_volatility = ctx.volatility().getText()
        elif keyword == "availabilityCriticality" and ctx.criticality():
            agg.availability_criticality = ctx.criticality().getText()
        elif keyword == "consistencyCriticality" and ctx.criticality():
            agg.consistency_criticality = ctx.criticality().getText()
        elif keyword == "storageSimilarity" and ctx.similarity():
            agg.storage_similarity = ctx.similarity().getText()
        elif keyword == "securityCriticality" and ctx.criticality():
            agg.security_criticality = ctx.criticality().getText()
        elif keyword == "securityZone" and ctx.STRING():
            agg.security_zone = self._strip_quotes(ctx.STRING().getText())
        elif keyword == "securityAccessGroup" and ctx.STRING():
            agg.security_access_group = self._strip_quotes(ctx.STRING().getText())

        return None

    def visitEntity(self, ctx: CMLParser.EntityContext):
        name = ctx.name(0).getText()
        entity = Entity(name=name)
        self._attach_comments(entity, ctx)

        if ctx.getChildCount() and ctx.getChild(0).getText() == "abstract":
            entity.is_abstract = True
        
        # Check extends
        if len(ctx.name()) > 1:
            entity.extends = ctx.name(1).getText()

        if ctx.traitRef():
            entity.traits = [t.name().getText() for t in ctx.traitRef()]
        
        if ctx.entityBody():
            if 'aggregateRoot' in ctx.entityBody().getText(): 
                 entity.is_aggregate_root = True

            # Process entity flags
            for flag in ctx.entityBody().entityFlag():
                negated = flag.notPrefix() is not None
                keyword = (
                    flag.getChild(flag.getChildCount() - 1).getText()
                    if negated
                    else flag.getChild(0).getText()
                )

                if keyword == "belongsTo" and flag.qualifiedName():
                    entity.belongs_to = flag.qualifiedName().getText()
                elif keyword == "validate" and flag.STRING():
                    entity.validate = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "package" and flag.qualifiedName():
                    entity.package = flag.qualifiedName().getText()
                elif keyword == "inheritanceType" and flag.STRING():
                    entity.inheritance_type = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "discriminatorColumn" and flag.STRING():
                    entity.discriminator_column = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "discriminatorValue" and flag.STRING():
                    entity.discriminator_value = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "discriminatorType" and flag.STRING():
                    entity.discriminator_type = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "discriminatorLength" and flag.STRING():
                    entity.discriminator_length = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "databaseTable" and flag.STRING():
                    entity.database_table = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "auditable":
                    entity.auditable = not negated
                elif keyword == "optimisticLocking":
                    entity.optimistic_locking = not negated
                elif keyword == "immutable":
                    entity.immutable = not negated
                elif keyword == "cache":
                    entity.cache = not negated
                elif keyword == "gap":
                    entity.gap_class = True
                elif keyword == "nogap":
                    entity.nogap_class = True
                elif keyword == "scaffold":
                    entity.scaffold = True
                elif keyword == "hint" and flag.STRING():
                    entity.hint = flag.STRING().getText().strip('"').strip("'")
            
            self.current_entity = entity
            for feature in ctx.entityBody().feature():
                self.visit(feature)
            self.current_entity = None

        # Merge traits (attributes/operations)
        self._merge_traits(entity)
        
        if self.current_aggregate:
            entity.aggregate = self.current_aggregate
            self.current_aggregate.entities.append(entity)
        elif hasattr(self, 'current_subdomain') and self.current_subdomain:
            self.current_subdomain.entities.append(entity)
        elif hasattr(self, 'current_module') and self.current_module:
            self.current_module.domain_objects.append(entity)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(entity)
            
        return entity

    def visitValueObject(self, ctx: CMLParser.ValueObjectContext):
        name = ctx.name(0).getText()
        vo = ValueObject(name=name)
        self._attach_comments(vo, ctx)

        if ctx.getChildCount() and ctx.getChild(0).getText() == "abstract":
            vo.is_abstract = True
        
        if len(ctx.name()) > 1:
            vo.extends = ctx.name(1).getText()

        if ctx.traitRef():
            vo.traits = [t.name().getText() for t in ctx.traitRef()]
        
        if ctx.valueObjectBody():
            for flag in ctx.valueObjectBody().valueObjectFlag():
                negated = flag.notPrefix() is not None
                keyword = (
                    flag.getChild(flag.getChildCount() - 1).getText()
                    if negated
                    else flag.getChild(0).getText()
                )

                if keyword == "belongsTo" and flag.qualifiedName():
                    vo.belongs_to = flag.qualifiedName().getText()
                elif keyword == "package" and flag.qualifiedName():
                    vo.package = flag.qualifiedName().getText()
                elif keyword == "validate" and flag.STRING():
                    vo.validate = self._strip_quotes(flag.STRING().getText())
                elif keyword == "gap":
                    vo.gap_class = True
                elif keyword == "nogap":
                    vo.nogap_class = True
                elif keyword == "scaffold":
                    vo.scaffold = True
                elif keyword == "hint" and flag.STRING():
                    vo.hint = self._strip_quotes(flag.STRING().getText())
                elif keyword == "immutable":
                    vo.immutable = not negated
                elif keyword == "persistent":
                    vo.persistent = not negated
                elif keyword == "cache":
                    vo.cache = not negated
                elif keyword == "optimisticLocking":
                    vo.optimistic_locking = not negated
                elif keyword == "aggregateRoot":
                    vo.is_aggregate_root = True
                elif keyword == "databaseTable" and flag.STRING():
                    vo.database_table = self._strip_quotes(flag.STRING().getText())
                elif keyword == "inheritanceType" and flag.STRING():
                    vo.inheritance_type = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorColumn" and flag.STRING():
                    vo.discriminator_column = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorValue" and flag.STRING():
                    vo.discriminator_value = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorType" and flag.STRING():
                    vo.discriminator_type = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorLength" and flag.STRING():
                    vo.discriminator_length = self._strip_quotes(flag.STRING().getText())

            self.current_value_object = vo
            for feature in ctx.valueObjectBody().feature():
                self.visit(feature)
            self.current_value_object = None

        # Merge traits (attributes/operations)
        self._merge_traits(vo)
            
        if self.current_aggregate:
            self.current_aggregate.value_objects.append(vo)
        elif hasattr(self, 'current_module') and self.current_module:
            self.current_module.domain_objects.append(vo)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(vo)
        return vo

    def visitDomainEvent(self, ctx: CMLParser.DomainEventContext):
        name = ctx.name(0).getText()
        de = DomainEvent(name=name)
        self._attach_comments(de, ctx)

        if ctx.getChildCount() and ctx.getChild(0).getText() == "abstract":
            de.is_abstract = True
        
        if len(ctx.name()) > 1:
            de.extends = ctx.name(1).getText()

        if ctx.traitRef():
            de.traits = [t.name().getText() for t in ctx.traitRef()]
        
        if ctx.domainEventBody():
            body = ctx.domainEventBody()
            if any(getattr(ch, "getText", lambda: None)() == "aggregateRoot" for ch in (body.children or [])):
                de.is_aggregate_root = True
            if any(getattr(ch, "getText", lambda: None)() == "persistent" for ch in (body.children or [])):
                de.persistent = True

            for flag in body.domainEventFlag():
                negated = flag.notPrefix() is not None
                keyword = (
                    flag.getChild(flag.getChildCount() - 1).getText()
                    if negated
                    else flag.getChild(0).getText()
                )

                if keyword == "belongsTo" and flag.qualifiedName():
                    de.belongs_to = flag.qualifiedName().getText()
                elif keyword == "package" and flag.qualifiedName():
                    de.package = flag.qualifiedName().getText()
                elif keyword == "validate" and flag.STRING():
                    de.validate = self._strip_quotes(flag.STRING().getText())
                elif keyword == "gap":
                    de.gap_class = True
                elif keyword == "nogap":
                    de.nogap_class = True
                elif keyword == "scaffold":
                    de.scaffold = True
                elif keyword == "hint" and flag.STRING():
                    de.hint = self._strip_quotes(flag.STRING().getText())
                elif keyword == "cache":
                    de.cache = not negated
                elif keyword == "databaseTable" and flag.STRING():
                    de.database_table = self._strip_quotes(flag.STRING().getText())
                elif keyword == "inheritanceType" and flag.STRING():
                    de.inheritance_type = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorColumn" and flag.STRING():
                    de.discriminator_column = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorValue" and flag.STRING():
                    de.discriminator_value = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorType" and flag.STRING():
                    de.discriminator_type = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorLength" and flag.STRING():
                    de.discriminator_length = self._strip_quotes(flag.STRING().getText())
                
            self.current_domain_event = de
            for feature in ctx.domainEventBody().feature():
                self.visit(feature)
            self.current_domain_event = None

        # Merge traits (attributes/operations)
        self._merge_traits(de)
            
        if self.current_application:
            self.current_application.domain_events.append(de)
        if self.current_aggregate:
            self.current_aggregate.domain_events.append(de)
        elif hasattr(self, 'current_module') and self.current_module:
            self.current_module.domain_objects.append(de)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(de)
        return de

    def visitEnumDecl(self, ctx: CMLParser.EnumDeclContext):
        name = ctx.name().getText()
        enum = Enum(name=name)
        self._attach_comments(enum, ctx)
        
        # Options
        for opt in ctx.enumOption():
            text = opt.getText()
            if text.startswith("aggregateLifecycle"):
                enum.is_aggregate_lifecycle = True
            elif text.startswith("ordinal"):
                enum.ordinal = True
            elif opt.qualifiedName() and opt.getChild(0).getText() == "package":
                enum.package = opt.qualifiedName().getText()
            elif opt.STRING() and opt.getChild(0).getText() == "hint":
                enum.hint = opt.STRING().getText().strip('"').strip("'")

        # Enum attributes
        for enum_attr_ctx in ctx.enumAttribute():
            attr = Attribute(
                name=enum_attr_ctx.name().getText(),
                type=enum_attr_ctx.type_().getText(),
                is_key=("key" in enum_attr_ctx.getText()),
            )
            enum.attributes.append(attr)

        # Enum values (ignore parameters for now, keep name list)
        enum.values = [v.name().getText() for v in ctx.enumValue()]
            
        if self.current_aggregate:
            self.current_aggregate.enums.append(enum)
        elif hasattr(self, 'current_module') and self.current_module:
            self.current_module.domain_objects.append(enum)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(enum)
        return enum

    def visitBasicType(self, ctx: CMLParser.BasicTypeContext):
        name = ctx.name().getText()
        basic_type = BasicType(name=name)
        self._attach_comments(basic_type, ctx)

        if ctx.traitRef():
            basic_type.traits = [t.name().getText() for t in ctx.traitRef()]

        body = getattr(ctx, "body", None) or ctx.basicTypeBody()
        if body:
            for flag in body.basicTypeFlag():
                negated = flag.notPrefix() is not None
                keyword = (
                    flag.getChild(flag.getChildCount() - 1).getText()
                    if negated
                    else flag.getChild(0).getText()
                )

                if keyword == "belongsTo" and flag.qualifiedName():
                    basic_type.belongs_to = flag.qualifiedName().getText()
                elif keyword == "package" and flag.qualifiedName():
                    basic_type.package = flag.qualifiedName().getText()
                elif keyword == "validate" and flag.STRING():
                    basic_type.validate = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "gap":
                    basic_type.gap_class = True
                elif keyword == "nogap":
                    basic_type.nogap_class = True
                elif keyword == "hint" and flag.STRING():
                    basic_type.hint = flag.STRING().getText().strip('"').strip("'")
                elif keyword == "immutable":
                    basic_type.immutable = not negated
                elif keyword == "cache":
                    basic_type.cache = not negated

            prev_holder = getattr(self, "current_value_object", None)
            self.current_value_object = basic_type
            for feature in body.feature():
                self.visit(feature)
            self.current_value_object = prev_holder

        # Merge traits (attributes/operations)
        self._merge_traits(basic_type)

        if self.current_aggregate:
            self.current_aggregate.basic_types.append(basic_type)
        elif self.current_module:
            self.current_module.domain_objects.append(basic_type)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(basic_type)
        return basic_type

    def _process_attribute(self, ctx):
        """Shared logic for processing attributes in both Java and Kotlin style.

        Both JavaStyleAttributeContext and KotlinStyleAttributeContext have:
        - attrName: NameContext
        - attrType: TypeContext
        - reference: Token (optional)
        - visibility(): VisibilityContext (optional)
        - attributeOption(): list of AttributeOptionContext
        - attributeAssociationLabel(): AttributeAssociationLabelContext (optional)
        """
        name = ctx.attrName.getText()
        type_name = ctx.attrType.getText()

        attr = Attribute(name=name, type=type_name)

        if ctx.reference:
            attr.is_reference = True
        if ctx.visibility():
            attr.visibility = ctx.visibility().getText()

        for child in ctx.getChildren():
            if child.getText() == 'key':
                attr.is_key = True
                break

        if ctx.attributeOption():
            for opt in ctx.attributeOption():
                self._apply_attribute_option(attr, opt)

        if ctx.attributeAssociationLabel() and ctx.attributeAssociationLabel().STRING():
            attr.association_label = self._strip_quotes(ctx.attributeAssociationLabel().STRING().getText())

        if hasattr(self, 'current_entity') and self.current_entity:
            self.current_entity.attributes.append(attr)
        elif hasattr(self, 'current_value_object') and self.current_value_object:
            self.current_value_object.attributes.append(attr)
        elif hasattr(self, 'current_domain_event') and self.current_domain_event:
            self.current_domain_event.attributes.append(attr)
        elif hasattr(self, 'current_association_holder') and self.current_association_holder:
            self.current_association_holder.attributes.append(attr)

        return attr

    def visitJavaStyleAttribute(self, ctx: CMLParser.JavaStyleAttributeContext):
        """Visit Java-style attribute: - Type name"""
        return self._process_attribute(ctx)

    def visitKotlinStyleAttribute(self, ctx: CMLParser.KotlinStyleAttributeContext):
        """Visit Kotlin-style attribute: - name: Type"""
        return self._process_attribute(ctx)

    def visitAssociation(self, ctx: CMLParser.AssociationContext):
        description = self._strip_quotes(ctx.STRING().getText()) if ctx.STRING() else None
        is_ref = getattr(ctx, "reference", None) is not None

        if not ctx.name():
            assoc = Association(target=ctx.type_().getText(), is_reference=is_ref, description=description)

            holder = None
            if getattr(self, "current_entity", None):
                holder = self.current_entity
            elif getattr(self, "current_value_object", None):
                holder = self.current_value_object
            elif getattr(self, "current_domain_event", None):
                holder = self.current_domain_event
            elif getattr(self, "current_service", None):
                holder = self.current_service

            if holder is not None and hasattr(holder, "associations"):
                holder.associations.append(assoc)
            return assoc

        # Backwards-compatible "named association" syntax: represent it as a reference attribute.
        name = ctx.name().getText()
        type_name = ctx.type_().getText()
        if is_ref:
            type_name = type_name if type_name.startswith("@") else f"@{type_name}"

        attr = Attribute(name=name, type=type_name, is_reference=True)
        if ctx.attributeOption():
            for opt in ctx.attributeOption():
                self._apply_attribute_option(attr, opt)

        holder = None
        if getattr(self, "current_entity", None):
            holder = self.current_entity
        elif getattr(self, "current_value_object", None):
            holder = self.current_value_object
        elif getattr(self, "current_domain_event", None):
            holder = self.current_domain_event

        if holder is not None and hasattr(holder, "attributes"):
            holder.attributes.append(attr)
        return attr

    def visitOperation(self, ctx: CMLParser.OperationContext):
        op_ctx = ctx.operationWithParams() or ctx.operationNoParams()
        name = op_ctx.name().getText()
        op = Operation(name=name)

        # Return type
        if getattr(op_ctx, "returnType", None):
            op.return_type = op_ctx.returnType.getText()

        # Visibility + abstract
        if hasattr(op_ctx, "visibility") and op_ctx.visibility():
            op.visibility = op_ctx.visibility().getText()
        elif hasattr(op_ctx, "operationPrefix") and op_ctx.operationPrefix() and op_ctx.operationPrefix().visibility():
            op.visibility = op_ctx.operationPrefix().visibility().getText()

        if hasattr(op_ctx, "operationPrefix") and op_ctx.operationPrefix() and "abstract" in op_ctx.operationPrefix().getText():
            op.is_abstract = True
        elif "abstract" in op_ctx.getText():
            op.is_abstract = True

        # Parameters (only possible for the with-params form)
        # Supports both Java-style (Type name) and Kotlin-style (name: Type)
        if hasattr(op_ctx, "parameterList") and op_ctx.parameterList():
            for param_ctx in op_ctx.parameterList().parameter():
                # Use labeled elements: paramName and paramType
                p_name = param_ctx.paramName.getText() if param_ctx.paramName else param_ctx.name().getText()
                p_type = param_ctx.paramType.getText() if param_ctx.paramType else param_ctx.type_().getText()
                is_ref = "@" in param_ctx.getText()
                op.parameters.append(Parameter(name=p_name, type=p_type, is_reference=is_ref))

        # Clauses (Xtext-style free ordering)
        if hasattr(op_ctx, "operationClause") and op_ctx.operationClause():
            for clause in op_ctx.operationClause():
                if clause.operationHint():
                    op.hint = clause.operationHint().operationHintType().getText()
                    if clause.operationHint().stateTransition():
                        op.state_transition = clause.operationHint().stateTransition().getText()
                    continue

                if clause.operationOption():
                    opt = clause.operationOption()
                    if opt.httpMethod():
                        op.http_method = opt.httpMethod().getText()
                        continue

                    key = opt.getChild(0).getText() if opt.getChildCount() else opt.getText()
                    if key == "hint" and opt.STRING():
                        op.hint_text = self._strip_quotes(opt.STRING().getText())
                    elif key == "path" and opt.STRING():
                        op.path = self._strip_quotes(opt.STRING().getText())
                    elif key == "return" and opt.STRING():
                        op.return_string = self._strip_quotes(opt.STRING().getText())
                    continue

                if clause.operationTail():
                    tail = clause.operationTail()
                    tail_text = tail.getText()
                    if tail.qualifiedName():
                        delegate_target = tail.qualifiedName().getText()
                        if "@" in tail_text and not delegate_target.startswith("@"):
                            delegate_target = f"@{delegate_target}"
                        op.delegate_target = delegate_target
                    elif tail.operationTarget():
                        target_ctx = tail.operationTarget()
                        if target_ctx.STRING():
                            target = self._strip_quotes(target_ctx.STRING().getText())
                        else:
                            target = target_ctx.getText()

                        if tail_text.startswith("publish"):
                            op.publishes_to = target
                            if tail.eventTypeRef():
                                op.publishes_event_type = tail.eventTypeRef().name().getText()
                            if tail.name():
                                op.publishes_event_bus = tail.name().getText()
                        elif tail_text.startswith("subscribe"):
                            op.subscribes_to = target
                            if tail.eventTypeRef():
                                op.subscribes_event_type = tail.eventTypeRef().name().getText()
                            if tail.name():
                                op.subscribes_event_bus = tail.name().getText()
                    continue

                if clause.throwsClause() and clause.throwsClause().qualifiedNameList():
                    qn_list_ctx = clause.throwsClause().qualifiedNameList()
                    op.throws = [t.getText() for t in qn_list_ctx.qualifiedName()]

        if hasattr(self, 'current_entity') and self.current_entity:
            self.current_entity.operations.append(op)
        elif hasattr(self, 'current_value_object') and self.current_value_object:
            self.current_value_object.operations.append(op)
        elif hasattr(self, 'current_domain_event') and self.current_domain_event:
            self.current_domain_event.operations.append(op)
        elif self.current_resource:
            self.current_resource.operations.append(op)
        elif hasattr(self, 'current_service') and self.current_service:
            self.current_service.operations.append(op)
        elif hasattr(self, 'current_repository') and self.current_repository:  # pragma: no cover
            self.current_repository.operations.append(op)
            
        return op

    def visitCallableOperationNoParens(self, ctx: CMLParser.CallableOperationNoParensContext):
        op = Operation(name=ctx.name().getText())

        if ctx.visibility():
            op.visibility = ctx.visibility().getText()

        if getattr(ctx, "returnType", None):
            op.return_type = ctx.returnType.getText()

        for clause in ctx.operationClause() or []:
            if clause.operationHint():
                op.hint = clause.operationHint().operationHintType().getText()
                if clause.operationHint().stateTransition():
                    op.state_transition = clause.operationHint().stateTransition().getText()
                continue

            if clause.operationOption():
                opt = clause.operationOption()
                if opt.httpMethod():
                    op.http_method = opt.httpMethod().getText()
                    continue

                key = opt.getChild(0).getText() if opt.getChildCount() else opt.getText()
                if key == "hint" and opt.STRING():
                    op.hint_text = self._strip_quotes(opt.STRING().getText())
                elif key == "path" and opt.STRING():
                    op.path = self._strip_quotes(opt.STRING().getText())
                elif key == "return" and opt.STRING():
                    op.return_string = self._strip_quotes(opt.STRING().getText())
                continue

            if clause.operationTail():
                tail = clause.operationTail()
                tail_text = tail.getText()
                if tail.qualifiedName():
                    delegate_target = tail.qualifiedName().getText()
                    if "@" in tail_text and not delegate_target.startswith("@"):
                        delegate_target = f"@{delegate_target}"
                    op.delegate_target = delegate_target
                elif tail.operationTarget():
                    target_ctx = tail.operationTarget()
                    if target_ctx.STRING():
                        target = self._strip_quotes(target_ctx.STRING().getText())
                    else:
                        target = target_ctx.getText()

                    if tail_text.startswith("publish"):
                        op.publishes_to = target
                        if tail.eventTypeRef():
                            op.publishes_event_type = tail.eventTypeRef().name().getText()
                        if tail.name():
                            op.publishes_event_bus = tail.name().getText()
                    elif tail_text.startswith("subscribe"):
                        op.subscribes_to = target
                        if tail.eventTypeRef():
                            op.subscribes_event_type = tail.eventTypeRef().name().getText()
                        if tail.name():
                            op.subscribes_event_bus = tail.name().getText()
                continue

            if clause.throwsClause() and clause.throwsClause().qualifiedNameList():
                qn_list_ctx = clause.throwsClause().qualifiedNameList()
                op.throws = [t.getText() for t in qn_list_ctx.qualifiedName()]

        if getattr(self, "current_resource", None):
            self.current_resource.operations.append(op)
        elif getattr(self, "current_service", None):
            self.current_service.operations.append(op)
        elif getattr(self, "current_repository", None):  # pragma: no cover
            self.current_repository.operations.append(op)

        return op

    def visitService(self, ctx: CMLParser.ServiceContext):
        name = ctx.name().getText()
        svc = Service(name=name)
        self._attach_comments(svc, ctx)
        prev_service = getattr(self, "current_service", None)
        self.current_service = svc
        self.visitChildren(ctx)
        self.current_service = prev_service
        
        if self.current_application:
            self.current_application.services.append(svc)
        if self.current_aggregate:
            svc.aggregate = self.current_aggregate
            self.current_aggregate.services.append(svc)
        elif self.current_module:
            self.current_module.services.append(svc)
        elif getattr(self, "current_subdomain", None):
            self.current_subdomain.services.append(svc)
        elif self.current_context:
            self.current_context.services.append(svc)
        elif self.current_tactic_application:
            self.current_tactic_application.services.append(svc)
            
        return svc

    def visitServiceModifier(self, ctx: CMLParser.ServiceModifierContext):
        if not getattr(self, "current_service", None):  # pragma: no cover
            return None

        svc = self.current_service
        text = ctx.getText()

        if ctx.STRING() and ctx.getChild(0).getText() == "hint":
            svc.hint = self._strip_quotes(ctx.STRING().getText())
            return None

        if text.startswith("subscribe"):
            if ctx.STRING():
                svc.subscribe_to = self._strip_quotes(ctx.STRING().getText())
            elif ctx.channelIdentifier():
                svc.subscribe_to = ctx.channelIdentifier().getText()
            if ctx.name():
                svc.subscribe_event_bus = ctx.name().getText()
        elif text == "gap":
            svc.gap_class = True
        elif text == "nogap":
            svc.nogap_class = True
        elif text == "webservice":
            svc.webservice = True
        elif text == "scaffold":
            svc.scaffold = True
        return None

    def visitResource(self, ctx: CMLParser.ResourceContext):
        name = ctx.name().getText()
        resource = Resource(name=name)
        self._attach_comments(resource, ctx)
        prev_resource = self.current_resource
        self.current_resource = resource
        self.visitChildren(ctx)
        self.current_resource = prev_resource

        if self.current_aggregate:
            resource.aggregate = self.current_aggregate
            self.current_aggregate.resources.append(resource)
        elif self.current_module:
            self.current_module.resources.append(resource)
        elif self.current_context:
            self.current_context.resources.append(resource)
        elif self.current_tactic_application:
            self.current_tactic_application.resources.append(resource)
        return resource

    def visitResourceModifier(self, ctx: CMLParser.ResourceModifierContext):
        if not getattr(self, "current_resource", None):  # pragma: no cover
            return None

        resource = self.current_resource
        text = ctx.getText()
        if ctx.STRING() and ctx.getChild(0).getText() == "hint":
            resource.hint = self._strip_quotes(ctx.STRING().getText())
        elif ctx.STRING() and ctx.getChild(0).getText() == "path":
            resource.path = self._strip_quotes(ctx.STRING().getText())
        elif text == "gap":
            resource.gap_class = True
        elif text == "nogap":
            resource.nogap_class = True
        elif text == "scaffold":
            resource.scaffold = True
        return None

    def visitConsumer(self, ctx: CMLParser.ConsumerContext):
        name = ctx.name().getText()
        consumer = Consumer(name=name)
        self._attach_comments(consumer, ctx)
        prev_consumer = self.current_consumer
        self.current_consumer = consumer
        self.visitChildren(ctx)
        self.current_consumer = prev_consumer

        if self.current_aggregate:
            consumer.aggregate = self.current_aggregate
            self.current_aggregate.consumers.append(consumer)
        elif self.current_module:
            self.current_module.consumers.append(consumer)
        elif self.current_context:
            self.current_context.consumers.append(consumer)
        elif self.current_tactic_application:
            self.current_tactic_application.consumers.append(consumer)
        return consumer

    def visitConsumerModifier(self, ctx: CMLParser.ConsumerModifierContext):
        if not getattr(self, "current_consumer", None):  # pragma: no cover
            return None

        consumer = self.current_consumer
        keyword = ctx.getChild(0).getText() if ctx.getChildCount() else ctx.getText()

        if keyword == "hint" and ctx.STRING():
            consumer.hint = self._strip_quotes(ctx.STRING().getText())
        elif keyword == "subscribe":
            if ctx.STRING():
                consumer.subscribe_to = self._strip_quotes(ctx.STRING().getText())
            elif ctx.channelIdentifier():
                consumer.subscribe_to = ctx.channelIdentifier().getText()
            if ctx.name():
                consumer.subscribe_event_bus = ctx.name().getText()
        elif keyword == "unmarshall" and ctx.qualifiedName():
            consumer.unmarshall_to = ctx.qualifiedName().getText()
        elif keyword in ("queueName", "topicName") and ctx.channelIdentifier():
            if keyword == "queueName":
                consumer.queue_name = ctx.channelIdentifier().getText()
            else:
                consumer.topic_name = ctx.channelIdentifier().getText()
        return None

    def visitDependency(self, ctx: CMLParser.DependencyContext):
        target = ctx.qualifiedName().getText()

        if getattr(self, "current_consumer", None):
            self.current_consumer.dependencies.append(target)
        elif getattr(self, "current_service", None):
            self.current_service.dependencies.append(target)
        elif getattr(self, "current_resource", None):
            self.current_resource.dependencies.append(target)
        elif getattr(self, "current_repository", None):
            self.current_repository.dependencies.append(target)
        return target

    def visitRepository(self, ctx: CMLParser.RepositoryContext):
        name = ctx.name().getText()
        repo = Repository(name=name)
        self._attach_comments(repo, ctx)
        prev_repo = getattr(self, "current_repository", None)
        self.current_repository = repo
        self.visitChildren(ctx)
        self.current_repository = prev_repo
        
        if self.current_aggregate:
            self.current_aggregate.repositories.append(repo)
            
        return repo

    def visitRepositoryModifier(self, ctx: CMLParser.RepositoryModifierContext):
        if not getattr(self, "current_repository", None):  # pragma: no cover
            return None

        repo = self.current_repository
        text = ctx.getText()
        if text.startswith("hint") and ctx.STRING():
            repo.hint = self._strip_quotes(ctx.STRING().getText())
        elif text.startswith("subscribe"):
            if ctx.STRING():
                repo.subscribe_to = self._strip_quotes(ctx.STRING().getText())
            elif ctx.channelIdentifier():
                repo.subscribe_to = ctx.channelIdentifier().getText()
            if ctx.name():
                repo.subscribe_event_bus = ctx.name().getText()
        elif text == "gap":
            repo.gap_class = True
        elif text == "nogap":
            repo.nogap_class = True
        return None

    def visitOwnerDecl(self, ctx: CMLParser.OwnerDeclContext):
        owner = ctx.name().getText()
        if self.current_aggregate:
            self.current_aggregate.owner = owner
        return owner

    def visitBoundedContextAttribute(self, ctx: CMLParser.BoundedContextAttributeContext):
        # Handle attributes like responsibilities, knowledgeLevel, etc.
        # These can apply to Context, Subdomain, or Aggregate
        
        target = None
        if self.current_aggregate:
            target = self.current_aggregate
        elif self.current_context:
            target = self.current_context
        elif self.current_subdomain:
            target = self.current_subdomain
        elif self.current_domain:
            target = self.current_domain
            
        if not target:  # pragma: no cover
            return
            
        if ctx.boundedContextType():
            if hasattr(target, 'type'):
                target.type = ctx.boundedContextType().getText()
                
        elif ctx.knowledgeLevel():
            if hasattr(target, 'knowledge_level'):
                target.knowledge_level = ctx.knowledgeLevel().getText()
                
        # Check for strings (responsibilities, vision, etc.)
        # Grammar: 'responsibilities' '=' STRING | 'domainVisionStatement' '=' STRING | ...
        
        text = ctx.getText()
        if 'responsibilities' in text:
            if ctx.STRING():  # pragma: no branch
                strings = ctx.STRING()
                if isinstance(strings, list):
                    values = [self._strip_quotes(s.getText()) for s in strings]
                    combined = ", ".join(values)
                else:
                    combined = self._strip_quotes(strings.getText())
                if hasattr(target, "responsibilities"):
                    target.responsibilities = combined
                    
        elif 'domainVisionStatement' in text:
            if ctx.STRING():  # pragma: no branch
                strings = ctx.STRING()
                s = (
                    self._strip_quotes(strings[0].getText())
                    if isinstance(strings, list)
                    else self._strip_quotes(strings.getText())
                )
                if hasattr(target, 'vision'):
                    target.vision = s
                    
        elif 'implementationTechnology' in text:
            if ctx.STRING():  # pragma: no branch
                strings = ctx.STRING()
                s = (
                    self._strip_quotes(strings[0].getText())
                    if isinstance(strings, list)
                    else self._strip_quotes(strings.getText())
                )
                if hasattr(target, 'implementation_technology'):
                    target.implementation_technology = s
        elif 'businessModel' in text:
            if ctx.STRING():
                strings = ctx.STRING()
                s = (
                    self._strip_quotes(strings[0].getText())
                    if isinstance(strings, list)
                    else self._strip_quotes(strings.getText())
                )
                if hasattr(target, 'business_model'):
                    target.business_model = s
        elif 'evolution' in text:
            if hasattr(target, 'evolution'):
                target.evolution = ctx.getText().split('=')[-1].strip()

    def visitSubdomainAttribute(self, ctx: CMLParser.SubdomainAttributeContext):
        if not self.current_subdomain:
            return
            
        if ctx.subdomainType():
            type_str = ctx.subdomainType().getText()
            try:
                self.current_subdomain.type = SubdomainType(type_str)
            except ValueError:  # pragma: no cover
                pass
                
        elif ctx.STRING():  # pragma: no cover
            # domainVisionStatement
            s = ctx.STRING().getText().strip('"')
            self.current_subdomain.vision = s

    def visitSetting(self, ctx: CMLParser.SettingContext):
        if getattr(self, "current_module", None) and ctx.qualifiedName():
            self.current_module.base_package = ctx.qualifiedName().getText()
        return None

    def visitModuleAttribute(self, ctx: CMLParser.ModuleAttributeContext):
        if not getattr(self, "current_module", None):
            return None

        text = ctx.getText()
        if text == "external":
            self.current_module.external = True
        elif text.startswith("hint") and ctx.STRING():
            self.current_module.hint = self._strip_quotes(ctx.STRING().getText())
        return None

    def visitRepositoryMethod(self, ctx: CMLParser.RepositoryMethodContext):
        name_ctx = ctx.name()
        name = name_ctx.getText() if name_ctx else None
        op = Operation(name=name)
        
        if ctx.type_():
            op.return_type = ctx.type_().getText()
            
        if ctx.visibility():
            op.visibility = ctx.visibility().getText()
            
        if ctx.parameterList():
            for param_ctx in ctx.parameterList().parameter():
                # Use labeled elements: paramName and paramType
                p_name = param_ctx.paramName.getText() if param_ctx.paramName else param_ctx.name().getText()
                p_type = param_ctx.paramType.getText() if param_ctx.paramType else param_ctx.type_().getText()
                is_ref = '@' in param_ctx.getText()
                op.parameters.append(Parameter(name=p_name, type=p_type, is_reference=is_ref))
                
        if ctx.repositoryMethodOption():
            for opt in ctx.repositoryMethodOption():
                text = opt.getText()
                keyword = opt.getChild(0).getText() if opt.getChildCount() else text

                if keyword == "throws" and opt.qualifiedNameList():
                    qn_list_ctx = opt.qualifiedNameList()
                    op.throws = [t.getText() for t in qn_list_ctx.qualifiedName()]
                elif keyword == "hint" and opt.STRING():
                    op.hint_text = self._strip_quotes(opt.STRING().getText())
                elif keyword == "cache":
                    op.cache = True
                elif keyword == "gap":
                    op.gap = True
                elif keyword == "nogap":
                    op.nogap = True
                elif keyword == "construct":
                    op.construct = True
                elif keyword == "build":
                    op.build = True
                elif keyword == "map":
                    op.map_flag = True
                elif keyword == "query":
                    op.query = opt.STRING().getText().strip('"').strip("'")
                elif keyword == "condition":
                    op.condition = opt.STRING().getText().strip('"').strip("'")
                elif keyword == "select":
                    op.select = opt.STRING().getText().strip('"').strip("'")
                elif keyword == "groupBy":
                    op.group_by = opt.STRING().getText().strip('"').strip("'")
                elif keyword == "orderBy":
                    op.order_by = opt.STRING().getText().strip('"').strip("'")
                elif keyword in ("delegates", "=>") and opt.qualifiedName():
                    delegate_target = opt.qualifiedName().getText()
                    if "@" in text and not delegate_target.startswith("@"):
                        delegate_target = f"@{delegate_target}"
                    op.delegate_target = delegate_target
                elif keyword == "publish" and opt.operationTarget():
                    target_ctx = opt.operationTarget()
                    if target_ctx.STRING():
                        op.publishes_to = self._strip_quotes(target_ctx.STRING().getText())
                    else:
                        op.publishes_to = target_ctx.getText()
                    if opt.eventTypeRef():
                        op.publishes_event_type = opt.eventTypeRef().name().getText()
                    if opt.name():
                        op.publishes_event_bus = opt.name().getText()
                elif keyword == "subscribe" and opt.operationTarget():
                    target_ctx = opt.operationTarget()
                    if target_ctx.STRING():
                        op.subscribes_to = self._strip_quotes(target_ctx.STRING().getText())
                    else:
                        op.subscribes_to = target_ctx.getText()
                    if opt.eventTypeRef():
                        op.subscribes_event_type = opt.eventTypeRef().name().getText()
                    if opt.name():
                        op.subscribes_event_bus = opt.name().getText()

        if self.current_repository:
            self.current_repository.operations.append(op)
        else:  # pragma: no cover
            pass
            
        return op

    def visitUseCase(self, ctx: CMLParser.UseCaseContext):
        name = ctx.name().getText()
        uc = UseCase(name=name)
        self._attach_comments(uc, ctx)
        
        for element in ctx.useCaseBody():
            if element.useCaseActor():
                uc.actor = self._strip_quotes(element.useCaseActor().STRING().getText())
            elif element.useCaseSecondaryActors():
                sec = element.useCaseSecondaryActors().STRING()
                if isinstance(sec, list):
                    uc.secondary_actors = [self._strip_quotes(t.getText()) for t in sec]
                else:
                    uc.secondary_actors = [self._strip_quotes(sec.getText())]
            elif element.useCaseBenefit():
                uc.benefit = self._strip_quotes(element.useCaseBenefit().STRING().getText())
            elif element.useCaseScope():
                uc.scope = self._strip_quotes(element.useCaseScope().STRING().getText())
            elif element.useCaseLevel():
                uc.level = self._strip_quotes(element.useCaseLevel().STRING().getText())
            elif element.useCaseInteractionsBlock():
                # Handle interactions block
                for item in element.useCaseInteractionsBlock().useCaseInteractionItem():
                    if item.urFeature():
                        uc.interactions.append(" ".join(c.getText() for c in item.urFeature().getChildren()))
                    elif item.useCaseReadOperation():
                        # Parse read operation - just store as string for now
                        read_op = item.useCaseReadOperation().getText()
                        uc.interactions.append(read_op)
                    elif item.STRING():
                        uc.interactions.append(self._strip_quotes(item.STRING().getText()))
                    elif item.useCaseInteractionId():
                        uc.interactions.append(item.useCaseInteractionId().getText())
                        
        self.cml.use_cases.append(uc)
        return uc

    def visitUserStory(self, ctx: CMLParser.UserStoryContext):
        story_name_ctx = ctx.name(0) if hasattr(ctx, "name") else None
        name = story_name_ctx.getText() if story_name_ctx else ctx.name().getText()
        us = UserStory(name=name)
        self._attach_comments(us, ctx)

        if len(ctx.name()) > 1:
            us.split_by = ctx.name(1).getText()

        xtext_bodies = ctx.userStoryXtextBody()
        if xtext_bodies:
            body = xtext_bodies[0] if isinstance(xtext_bodies, list) else xtext_bodies
            if getattr(body, "role", None):
                us.role = self._strip_quotes(body.role.text)
            if getattr(body, "benefit", None):
                us.benefit = self._strip_quotes(body.benefit.text)

            us.features = []
            for feat in body.urFeature():
                story_feat = feat.urStoryFeature()
                if story_feat and story_feat.STRING():
                    us.features.append(self._strip_quotes(story_feat.STRING().getText()))
                else:
                    us.features.append(" ".join(c.getText() for c in feat.getChildren()))
            if us.features:
                us.feature = us.features[0]

            valuation = body.storyValuation()
            if valuation:
                promoted = getattr(valuation, "promoted", []) or []
                harmed = getattr(valuation, "harmed", []) or []
                us.promoted_values = [self._strip_quotes(t.text) for t in promoted]
                us.harmed_values = [self._strip_quotes(t.text) for t in harmed]

            self.cml.user_stories.append(us)
            return us
        
        bodies = ctx.userStoryBody()
        if bodies:
            body = bodies[0]
            
            # 'As' 'a' STRING
            # 'I' 'want' 'to' (ID | 'do')? STRING
            # 'so' 'that' STRING
            
            strings = body.STRING()
            if len(strings) >= 1:
                us.role = strings[0].getText().strip('"')
            if len(strings) >= 2:
                us.feature = strings[1].getText().strip('"')
            if len(strings) >= 3:
                us.benefit = strings[2].getText().strip('"')
                
        self.cml.user_stories.append(us)
        return us

    def visitStakeholderSection(self, ctx: CMLParser.StakeholderSectionContext):
        contexts: List[str] = []
        if ctx.idList():
            contexts = [n.getText() for n in ctx.idList().name()]

        section = StakeholderSection(contexts=contexts)
        prev_section = getattr(self, "current_stakeholder_section", None)
        self.current_stakeholder_section = section

        if ctx.stakeholderItem():
            for item in ctx.stakeholderItem():
                obj = self.visit(item)
                if isinstance(obj, StakeholderGroup):
                    section.stakeholder_groups.append(obj)
                elif isinstance(obj, Stakeholder):
                    section.stakeholders.append(obj)

        self.current_stakeholder_section = prev_section
        self.cml.stakeholder_sections.append(section)
        return section

    def visitStakeholderGroup(self, ctx: CMLParser.StakeholderGroupContext):
        name = ctx.name().getText()
        group = StakeholderGroup(name=name)
        
        self.current_stakeholder_group = group
        if ctx.stakeholder():
            for s in ctx.stakeholder():
                self.visit(s)
        self.current_stakeholder_group = None
        
        self.cml.stakeholder_groups.append(group)
        return group

    def visitStakeholder(self, ctx: CMLParser.StakeholderContext):
        name = ctx.name().getText()
        stakeholder = Stakeholder(name=name)
        
        if ctx.stakeholderAttribute():
            for attr in ctx.stakeholderAttribute():
                text = attr.getText()
                if 'influence' in text:
                    stakeholder.influence = attr.name().getText()
                elif 'interest' in text:
                    stakeholder.interest = attr.name().getText()
                elif 'priority' in text:
                    stakeholder.priority = attr.name().getText()
                elif 'impact' in text:
                    stakeholder.impact = attr.name().getText()
                elif 'description' in text and attr.STRING():
                    stakeholder.description = self._strip_quotes(attr.STRING().getText())
                elif attr.consequences():
                    for item in attr.consequences().consequenceItem():
                        stakeholder.consequences.append(item.getText())
                elif attr.consequenceItem():
                    stakeholder.consequences.append(attr.consequenceItem().getText())

        if self.current_stakeholder_group:
            self.current_stakeholder_group.stakeholders.append(stakeholder)
        elif self.current_value_cluster:
             # Value stakeholders are just references usually, but grammar allows full definition
             # We'll just add them to the main list if they are full definitions
             pass
        else:
            self.cml.stakeholders.append(stakeholder)
            
        return stakeholder

    def visitValueRegister(self, ctx: CMLParser.ValueRegisterContext):
        name = ctx.name(0).getText()
        register = ValueRegister(name=name)
        self._attach_comments(register, ctx)
        
        if len(ctx.name()) > 1:
            register.context = ctx.name(1).getText()
            
        self.current_value_register = register
        
        for cluster in ctx.valueCluster():
            self.visit(cluster)
            
        for value in ctx.value():
            self.visit(value)

        if hasattr(ctx, "valueEpic"):
            for epic in ctx.valueEpic():
                self.visit(epic)

        if hasattr(ctx, "valueWeigthing"):
            for vw in ctx.valueWeigthing():
                self.visit(vw)

        if hasattr(ctx, "valueNarrative"):
            for vn in ctx.valueNarrative():
                self.visit(vn)
            
        self.current_value_register = None
        self.cml.value_registers.append(register)
        return register

    def visitValueCluster(self, ctx: CMLParser.ValueClusterContext):
        name = ctx.name().getText()
        cluster = ValueCluster(name=name)
        
        if ctx.valueClusterAttribute():
            for attr in ctx.valueClusterAttribute():
                text = attr.getText()
                if text.startswith("core"):
                    if attr.STRING():
                        cluster.core_value = self._strip_quotes(attr.STRING().getText())
                    elif attr.name():
                        cluster.core_value = attr.name().getText()
                elif text.startswith("demonstrator") and attr.STRING():
                    d = self._strip_quotes(attr.STRING().getText())
                    cluster.demonstrators.append(d)
                    cluster.demonstrator = cluster.demonstrator or d
                elif text.startswith("relatedValue") and attr.STRING():
                    cluster.related_values.append(self._strip_quotes(attr.STRING().getText()))
                elif text.startswith("opposingValue") and attr.STRING():
                    cluster.opposing_values.append(self._strip_quotes(attr.STRING().getText()))
                    
        self.current_value_cluster = cluster
        for value in ctx.value():
            self.visit(value)
        if hasattr(ctx, "valueElicitation") and ctx.valueElicitation():
            for elic_ctx in ctx.valueElicitation():
                elic = self.visit(elic_ctx)
                if elic:
                    cluster.elicitations.append(elic)
        self.current_value_cluster = None
        
        if self.current_value_register:
            self.current_value_register.clusters.append(cluster)
            
        return cluster

    def visitValue(self, ctx: CMLParser.ValueContext):
        name = ctx.name().getText()
        value = Value(name=name)
        
        if ctx.valueAttribute():
            for attr in ctx.valueAttribute():
                text = attr.getText()
                if text.startswith("core") or text.startswith("isCore"):
                    value.is_core = True
                elif text.startswith("demonstrator") and attr.STRING():
                    d = self._strip_quotes(attr.STRING().getText())
                    value.demonstrators.append(d)
                    value.demonstrator = value.demonstrator or d
                elif text.startswith("relatedValue") and attr.STRING():
                    value.related_values.append(self._strip_quotes(attr.STRING().getText()))
                elif text.startswith("opposingValue") and attr.STRING():
                    value.opposing_values.append(self._strip_quotes(attr.STRING().getText()))

        if hasattr(ctx, "valueElicitation") and ctx.valueElicitation():
            for elic_ctx in ctx.valueElicitation():
                elic = self.visit(elic_ctx)
                if not elic:
                    continue
                value.elicitations.append(elic)
                if elic.stakeholder and not any(s.name == elic.stakeholder for s in value.stakeholders):
                    value.stakeholders.append(Stakeholder(name=elic.stakeholder))

        if self.current_value_cluster:
            self.current_value_cluster.values.append(value)
        elif self.current_value_register:
            self.current_value_register.values.append(value)
            
        return value

    def visitValueElicitation(self, ctx: CMLParser.ValueElicitationContext):
        stakeholder_name = ctx.name().getText()
        elicitation = ValueElicitation(stakeholder=stakeholder_name)

        if hasattr(ctx, "valueElicitationOption") and ctx.valueElicitationOption():
            for opt in ctx.valueElicitationOption():
                text = opt.getText()
                if text.startswith("priority") and opt.name():
                    elicitation.priority = opt.name().getText()
                elif text.startswith("impact") and opt.name():
                    elicitation.impact = opt.name().getText()
                elif text.startswith("consequences") and opt.valueConsequenceEntry():
                    last: Optional[ValueConsequence] = None
                    for entry in opt.valueConsequenceEntry():
                        if entry.valueConsequence() and entry.valueConsequence().STRING():
                            cctx = entry.valueConsequence()
                            kind = cctx.getChild(0).getText()
                            consequence_text = self._strip_quotes(cctx.STRING().getText())
                            last = ValueConsequence(kind=kind, consequence=consequence_text)
                            elicitation.consequences.append(last)
                        elif entry.valueAction() and entry.valueAction().STRING():
                            act_ctx = entry.valueAction()
                            action_text = self._strip_quotes(act_ctx.STRING(0).getText())
                            action_type = None
                            if act_ctx.name():
                                action_type = act_ctx.name().getText()
                            elif act_ctx.STRING(1):  # type provided as quoted string
                                action_type = self._strip_quotes(act_ctx.STRING(1).getText())
                            action = ValueAction(action=action_text, type=action_type)
                            if last and last.action is None:
                                last.action = action
                            else:
                                elicitation.consequences.append(
                                    ValueConsequence(kind="action", consequence=action_text, action=action)
                                )

        return elicitation

    def visitValueEpic(self, ctx: CMLParser.ValueEpicContext):
        names_ctx = ctx.name()
        name_list = []
        if isinstance(names_ctx, list):
            name_list = names_ctx
        elif names_ctx:
            name_list = [names_ctx]

        epic = ValueEpic(name=name_list[0].getText() if name_list else "")
        if len(name_list) >= 2:
            epic.stakeholder = name_list[1].getText()

        value_token = ctx.STRING()
        if value_token:
            epic.value = self._strip_quotes(value_token.getText())

        for clause in ctx.valueEpicClause() or []:
            kind = clause.getChild(0).getText()
            clause_value_token = clause.STRING()
            if not clause_value_token:  # pragma: no cover
                continue
            clause_value = self._strip_quotes(clause_value_token.getText())
            if kind == "realization":
                epic.realized.append(clause_value)
            elif kind == "reduction":
                epic.reduced.append(clause_value)
        if self.current_value_register:
            self.current_value_register.epics.append(epic)
        return epic

    def visitValueNarrative(self, ctx: CMLParser.ValueNarrativeContext):
        name_ctx = ctx.name()
        name_node = name_ctx[0] if isinstance(name_ctx, list) else name_ctx
        narrative = ValueNarrative(name=name_node.getText() if name_node else "")
        strings = [s.getText().strip('"').strip("'") for s in ctx.STRING()]
        if len(strings) >= 4:
            narrative.feature = strings[0]
            narrative.promoted = strings[1]
            narrative.harmed = strings[2]
            narrative.behavior = strings[3]
        if self.current_value_register:
            self.current_value_register.narratives.append(narrative)
        return narrative

    def visitValueWeigthing(self, ctx: CMLParser.ValueWeigthingContext):
        name_ctx = ctx.name()
        name_node = name_ctx[0] if isinstance(name_ctx, list) else name_ctx
        vw = ValueWeigthing(name=name_node.getText() if name_node else "")
        strings = [s.getText().strip('"').strip("'") for s in ctx.STRING()]
        names_ctx = ctx.name()
        name_list = []
        if isinstance(names_ctx, list):
            name_list = names_ctx
        elif names_ctx:
            name_list = [names_ctx]
        if len(name_list) > 1:
            vw.stakeholder = name_list[1].getText()
        if len(strings) >= 2:
            vw.more_than = (strings[0], strings[1])
        if len(strings) >= 3:
            vw.benefits = strings[2]
        if len(strings) >= 4:
            vw.harms = strings[3]
        if self.current_value_register:
            self.current_value_register.weightings.append(vw)
        return vw

    # --- ServiceCutter DSL (minimal) ---

    def visitScAggregate(self, ctx: CMLParser.ScAggregateContext):
        name_token = ctx.STRING(0) or ctx.ID(0)
        name = name_token.getText().strip('"').strip("'")
        nanoentities = []
        strings = ctx.STRING()
        if strings:
            for s in strings[1:]:
                nanoentities.append(s.getText().strip('"').strip("'"))
        self.service_cutter.aggregates.append(SCAggregate(name=name, nanoentities=nanoentities))
        return None

    def visitScEntity(self, ctx: CMLParser.ScEntityContext):
        name = ctx.STRING(0).getText().strip('"').strip("'")
        nanoentities = [s.getText().strip('"').strip("'") for s in ctx.STRING()[1:]]
        self.service_cutter.entities.append(SCEntity(name=name, nanoentities=nanoentities))
        return None

    def visitScSecurityAccessGroup(self, ctx: CMLParser.ScSecurityAccessGroupContext):
        name_token = ctx.STRING(0) or ctx.ID(0)
        name = name_token.getText().strip('"').strip("'")
        nanoentities = []
        strings = ctx.STRING()
        if strings:
            for s in strings[1:]:
                nanoentities.append(s.getText().strip('"').strip("'"))
        self.service_cutter.security_access_groups.append(SCSecurityAccessGroup(name=name, nanoentities=nanoentities))
        return None

    def visitScSeparatedSecurityZone(self, ctx: CMLParser.ScSeparatedSecurityZoneContext):
        name = ctx.STRING(0).getText().strip('"').strip("'")
        nanoentities = [s.getText().strip('"').strip("'") for s in ctx.STRING()[1:]]
        self.service_cutter.separated_security_zones.append(
            SCSeparatedSecurityZone(name=name, nanoentities=nanoentities)
        )
        return None

    def visitScSharedOwnerGroup(self, ctx: CMLParser.ScSharedOwnerGroupContext):
        name = ctx.STRING(0).getText().strip('"').strip("'")
        nanoentities = [s.getText().strip('"').strip("'") for s in ctx.STRING()[1:]]
        self.service_cutter.shared_owner_groups.append(
            SCSharedOwnerGroup(name=name, nanoentities=nanoentities)
        )
        return None

    def visitScPredefinedService(self, ctx: CMLParser.ScPredefinedServiceContext):
        name = ctx.STRING(0).getText().strip('"').strip("'")
        nanoentities = [s.getText().strip('"').strip("'") for s in ctx.STRING()[1:]]
        self.service_cutter.predefined_services.append(
            SCPredefinedService(name=name, nanoentities=nanoentities)
        )
        return None

    def visitScCompatibilities(self, ctx: CMLParser.ScCompatibilitiesContext):
        raw = ctx.getText()
        compat = SCCompatibilities(raw=raw)
        if self.service_cutter.compatibilities is not None:
            raise ValueError("Compatibilities can only be defined once in ServiceCutter DSL.")
        if ctx.scCharacteristic():
            for ch in ctx.scCharacteristic():
                self.visit(ch)
        self.service_cutter.compatibilities = compat
        return None

    def visitScUseCase(self, ctx: CMLParser.ScUseCaseContext):
        name = ctx.name().getText()

        # The grammar's scUseCase alternative also matches a plain
        # 'UseCase Name { }' with an empty body (it appears before useCase
        # in topLevel). Treat such empty-bodied use cases as regular CML
        # use cases instead of ServiceCutter configuration.
        if not ctx.scUseCaseElement():
            uc = UseCase(name=name)
            self._attach_comments(uc, ctx)
            self.cml.use_cases.append(uc)
            return uc

        uc = SCUseCase(name=name, raw=ctx.getText())

        for element in ctx.scUseCaseElement():
            if element.scIsLatencyCritical():
                uc.is_latency_critical = True
                continue

            reads = element.scReads()
            if reads and reads.scUseCaseNanoentities():
                uc.reads = [
                    s.getText().strip('"').strip("'")
                    for s in reads.scUseCaseNanoentities().STRING()
                ]
                continue
            if reads:
                uc.reads = []
                continue

            writes = element.scWrites()
            if writes and writes.scUseCaseNanoentities():
                uc.writes = [
                    s.getText().strip('"').strip("'")
                    for s in writes.scUseCaseNanoentities().STRING()
                ]
                continue
            if writes:
                uc.writes = []
                continue

        self.service_cutter.use_cases.append(uc)
        return None

    def visitScAvailabilityCriticality(self, ctx: CMLParser.ScAvailabilityCriticalityContext):
        self._visitCharacteristic("AvailabilityCriticality", ctx)
        return None

    def visitScConsistencyCriticality(self, ctx: CMLParser.ScConsistencyCriticalityContext):
        self._visitCharacteristic("ConsistencyCriticality", ctx)
        return None

    def visitScContentVolatility(self, ctx: CMLParser.ScContentVolatilityContext):
        self._visitCharacteristic("ContentVolatility", ctx)
        return None

    def visitScSecurityCriticality(self, ctx: CMLParser.ScSecurityCriticalityContext):
        self._visitCharacteristic("SecurityCriticality", ctx)
        return None

    def visitScStorageSimilarity(self, ctx: CMLParser.ScStorageSimilarityContext):
        self._visitCharacteristic("StorageSimilarity", ctx)
        return None

    def visitScStructuralVolatility(self, ctx: CMLParser.ScStructuralVolatilityContext):
        self._visitCharacteristic("StructuralVolatility", ctx)
        return None

    def _visitCharacteristic(self, type_name, ctx):
        char_name = ctx.name().getText() if hasattr(ctx, "name") and ctx.name() else None
        nanos = []
        if ctx.scNanoentities():
            nanos = [s.getText().strip('"').strip("'") for s in ctx.scNanoentities().STRING()]
        self.service_cutter.characteristics.append(SCCharacteristic(type=type_name, characteristic=char_name, nanoentities=nanos))

    def visitApplication(self, ctx: CMLParser.ApplicationContext):
        app_name = ctx.name().getText() if ctx.name() else None
        app = Application(name=app_name)
        self._attach_comments(app, ctx)
        self.current_application = app
        
        for element in ctx.applicationElement():
            if element.commandDecl():
                cmd_name = element.commandDecl().name().getText()
                app.commands.append(Command(name=cmd_name))
            elif element.commandEvent():
                self.visit(element.commandEvent())
            elif element.domainEvent():
                self.visit(element.domainEvent())
            elif element.flow():
                self.visit(element.flow())
            elif element.service():
                self.visit(element.service())
            elif element.coordination():
                self.visit(element.coordination())
                
        if self.current_module:
            self.current_module.application = app
        elif self.current_context:
            self.current_context.application = app
        else:
            pass
            
        self.current_application = None
        return app

    def visitFlow(self, ctx: CMLParser.FlowContext):
        name = ctx.name().getText()
        flow = Flow(name=name)
        
        for step in ctx.flowStep():
            flow_step = None
            if step.flowCommandStep():
                s = step.flowCommandStep()
                s_name = s.name().getText()
                flow_step = FlowStep(type="command", name=s_name)
                if s.flowInitiator() and s.flowInitiator().STRING():
                    flow_step.initiated_by = self._strip_quotes(s.flowInitiator().STRING().getText())
                if s.flowCommandTail():
                    tail = s.flowCommandTail()
                    if tail.flowDelegate():
                        flow_step.delegate = tail.flowDelegate().name().getText()
                        if tail.flowDelegate().stateTransition():
                            flow_step.delegate_state_transition = tail.flowDelegate().stateTransition().getText()
                    if tail.flowEmitsClause():
                        # emits event A + B
                        if tail.flowEmitsClause().flowEventList():
                            ev_list = tail.flowEmitsClause().flowEventList()
                            flow_step.emits = [n.getText() for n in ev_list.name()]
                            flow_step.emit_connectors = [op.getText() for op in ev_list.transitionOperator()]
                             
            elif step.flowEventStep():
                s = step.flowEventStep()
                # event A + B triggers ...
                trig_list = s.flowEventTriggerList()
                triggers = [n.getText() for n in trig_list.name()]
                trigger_connectors = [op.getText() for op in trig_list.transitionOperator()]

                inv_list = s.flowInvocationList()

                def _inv_parts(inv_ctx):
                    kind = inv_ctx.flowInvocationKind().getText() if inv_ctx.flowInvocationKind() else None
                    return kind, inv_ctx.name().getText()

                first_inv = inv_list.flowInvocation()
                first_kind, first_name = _inv_parts(first_inv)
                invocations = [first_name]
                invocation_kinds = [first_kind]
                invocation_connectors = []

                for conn in inv_list.flowInvocationConnector():
                    invocation_connectors.append(conn.transitionOperator().getText())
                    kind, name_ = _inv_parts(conn.flowInvocation())
                    invocations.append(name_)
                    invocation_kinds.append(kind)

                # Keep backward compatibility: `name` is first invoked action.
                flow_step = FlowStep(type="event", name=invocations[0])
                flow_step.triggers = triggers
                flow_step.trigger_connectors = trigger_connectors
                flow_step.invocations = invocations
                flow_step.invocation_kinds = invocation_kinds
                flow_step.invocation_connectors = invocation_connectors
                
            elif step.flowOperationStep():
                s = step.flowOperationStep()
                s_name = s.name().getText()
                flow_step = FlowStep(type="operation", name=s_name)
                if s.flowInitiator() and s.flowInitiator().STRING():
                    flow_step.initiated_by = self._strip_quotes(s.flowInitiator().STRING().getText())
                if s.flowOperationTail():
                    tail = s.flowOperationTail()
                    if tail.flowDelegate():
                        flow_step.delegate = tail.flowDelegate().name().getText()
                        if tail.flowDelegate().stateTransition():
                            flow_step.delegate_state_transition = tail.flowDelegate().stateTransition().getText()
                    if tail.flowEmitsClause():
                        if tail.flowEmitsClause().flowEventList():
                            ev_list = tail.flowEmitsClause().flowEventList()
                            flow_step.emits = [n.getText() for n in ev_list.name()]
                            flow_step.emit_connectors = [op.getText() for op in ev_list.transitionOperator()]

            if flow_step:
                flow.steps.append(flow_step)

        if self.current_application:
            self.current_application.flows.append(flow)
        return flow

    def visitCoordination(self, ctx: CMLParser.CoordinationContext):
        name = ctx.name().getText()
        coord = Coordination(name=name)
        
        for step in ctx.coordinationStep():
            path = step.coordinationPath().getText()
            coord.steps.append(path)
            parts = [n.getText() for n in step.coordinationPath().name()]
            if len(parts) >= 3:
                step_ref = CoordinationStepRef(
                    bounded_context=parts[0],
                    service=parts[1],
                    operation=parts[2],
                )
                step_ref.bounded_context_ref = self._get_or_create_context(parts[0])
                coord.step_refs.append(step_ref)
            
        if self.current_application:
            self.current_application.coordinations.append(coord)
        return coord

    def visitModule(self, ctx: CMLParser.ModuleContext):
        name = ctx.name().getText()
        module = Module(name=name)
        self._attach_comments(module, ctx)
        
        self.current_module = module
        if ctx.body:
            self.visit(ctx.body)
        self.current_module = None
        
        if self.current_context:
            self.current_context.modules.append(module)
        return module

    def visitCommandEvent(self, ctx: CMLParser.CommandEventContext):
        name = ctx.name(0).getText()
        ce = CommandEvent(name=name)
        self._attach_comments(ce, ctx)

        if ctx.getChildCount() and ctx.getChild(0).getText() == "abstract":
            ce.is_abstract = True
        
        if len(ctx.name()) > 1:
            ce.extends = ctx.name(1).getText()

        if ctx.traitRef():
            ce.traits = [t.name().getText() for t in ctx.traitRef()]
            
        body = getattr(ctx, "body", None) or ctx.commandEventBody()
        if body:
            for flag in body.commandEventFlag():
                negated = flag.notPrefix() is not None
                keyword = (
                    flag.getChild(flag.getChildCount() - 1).getText()
                    if negated
                    else flag.getChild(0).getText()
                )

                if keyword == "belongsTo" and flag.qualifiedName():
                    ce.belongs_to = flag.qualifiedName().getText()
                elif keyword == "package" and flag.qualifiedName():
                    ce.package = flag.qualifiedName().getText()
                elif keyword == "validate" and flag.STRING():
                    ce.validate = self._strip_quotes(flag.STRING().getText())
                elif keyword == "gap":
                    ce.gap_class = True
                elif keyword == "nogap":
                    ce.nogap_class = True
                elif keyword == "scaffold":
                    ce.scaffold = True
                elif keyword == "hint" and flag.STRING():
                    ce.hint = self._strip_quotes(flag.STRING().getText())
                elif keyword == "cache":
                    ce.cache = not negated
                elif keyword == "persistent":
                    ce.persistent = True
                elif keyword == "aggregateRoot":
                    ce.is_aggregate_root = True
                elif keyword == "databaseTable" and flag.STRING():
                    ce.database_table = self._strip_quotes(flag.STRING().getText())
                elif keyword == "inheritanceType" and flag.STRING():
                    ce.inheritance_type = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorColumn" and flag.STRING():
                    ce.discriminator_column = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorValue" and flag.STRING():
                    ce.discriminator_value = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorType" and flag.STRING():
                    ce.discriminator_type = self._strip_quotes(flag.STRING().getText())
                elif keyword == "discriminatorLength" and flag.STRING():
                    ce.discriminator_length = self._strip_quotes(flag.STRING().getText())

            prev_domain_event = getattr(self, "current_domain_event", None)
            self.current_domain_event = ce  # Reuse domain event logic for attributes/ops
            for feature in body.feature():
                self.visit(feature)
            self.current_domain_event = prev_domain_event

        # Merge traits (attributes/operations)
        for trait_name in ce.traits:
            trait_obj = self.trait_map.get(trait_name)
            if not trait_obj:
                continue
            existing_attr_names = {a.name for a in ce.attributes}
            for attr in trait_obj.attributes:
                if attr.name not in existing_attr_names:
                    ce.attributes.append(attr)
            existing_op_names = {o.name for o in ce.operations}
            for op in trait_obj.operations:
                if op.name not in existing_op_names:
                    ce.operations.append(op)
            existing_assoc_keys = {(a.target, a.is_reference, a.description) for a in getattr(ce, "associations", [])}
            for assoc in getattr(trait_obj, "associations", []) or []:
                key = (assoc.target, assoc.is_reference, assoc.description)
                if key in existing_assoc_keys:
                    continue
                ce.associations.append(
                    Association(target=assoc.target, is_reference=assoc.is_reference, description=assoc.description)
                )
                existing_assoc_keys.add(key)
            
        if self.current_application:
            self.current_application.command_events.append(ce)
        if self.current_aggregate:
            self.current_aggregate.command_events.append(ce)
        elif self.current_module:
            self.current_module.domain_objects.append(ce)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(ce)
        return ce

    def visitDataTransferObject(self, ctx: CMLParser.DataTransferObjectContext):
        name = ctx.name(0).getText()
        dto = DataTransferObject(name=name)
        self._attach_comments(dto, ctx)
        
        if len(ctx.name()) > 1:
            dto.extends = ctx.name(1).getText()

        # Modifiers before body
        if ctx.dtoModifier():
            for mod in ctx.dtoModifier():
                text = mod.getText()
                if text == "gap":
                    dto.gap_class = True
                elif text == "nogap":
                    dto.nogap_class = True
                elif text == "scaffold":
                    dto.scaffold = True
                elif mod.STRING() and mod.getChild(0).getText() == "hint":
                    dto.hint = mod.STRING().getText().strip('"').strip("'")
                elif mod.STRING() and mod.getChild(0).getText() == "validate":
                    dto.validate = mod.STRING().getText().strip('"').strip("'")

        if ctx.body:
            # Flags inside body
            for flag in ctx.body.dtoFlag():
                text = flag.getText()
                if flag.qualifiedName() and flag.getChild(0).getText() == "package":
                    dto.package = flag.qualifiedName().getText()
                elif text == "gap":
                    dto.gap_class = True
                elif text == "nogap":
                    dto.nogap_class = True
                elif text == "scaffold":
                    dto.scaffold = True
                elif flag.STRING() and flag.getChild(0).getText() == "hint":
                    dto.hint = flag.STRING().getText().strip('"').strip("'")
                elif flag.getChild(0).getText() == "validate":
                    if flag.STRING():
                        dto.validate = flag.STRING().getText().strip('"').strip("'")

            # Features (attributes/operations/associations)
            self.current_value_object = dto
            for feature in ctx.body.feature():
                self.visit(feature)
            self.current_value_object = None
            
        if self.current_aggregate:
            self.current_aggregate.data_transfer_objects.append(dto)
        elif self.current_module:
            self.current_module.domain_objects.append(dto)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(dto)
        return dto

    def visitTrait(self, ctx: CMLParser.TraitContext):
        name = ctx.name().getText()
        trait = Trait(name=name)
        self._attach_comments(trait, ctx)

        if ctx.traitBody():
            for flag in ctx.traitBody().traitFlag():
                if flag.qualifiedName() and flag.getChild(0).getText() == "package":
                    trait.package = flag.qualifiedName().getText()
                elif flag.STRING() and flag.getChild(0).getText() == "hint":
                    trait.hint = flag.STRING().getText().strip('"').strip("'")

            # Reuse attribute/operation handling via current_value_object placeholder
            self.current_value_object = trait
            for feature in ctx.traitBody().feature():
                self.visit(feature)
            self.current_value_object = None

        if self.current_module:
            self.current_module.domain_objects.append(trait)
        elif self.current_tactic_application:
            self.current_tactic_application.domain_objects.append(trait)
        self.trait_map[name] = trait
        self.cml.traits.append(trait)
        return trait
