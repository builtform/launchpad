# Component Architecture & Composition — HIGH

Composition patterns for building flexible, maintainable React components. Avoid boolean prop proliferation by using compound components, lifting state, and composing internals.

---

## composition-avoid-boolean-props — No Boolean Prop Proliferation

**Impact: CRITICAL (prevents unmaintainable component variants)**

Each boolean doubles possible states. Use composition instead.

**Incorrect: boolean props create exponential complexity**

```tsx
function Composer({
  onSubmit,
  isThread,
  channelId,
  isDMThread,
  dmId,
  isEditing,
  isForwarding,
}: Props) {
  return (
    <form>
      <Header />
      <Input />
      {isDMThread ? (
        <AlsoSendToDMField id={dmId} />
      ) : isThread ? (
        <AlsoSendToChannelField id={channelId} />
      ) : null}
      {isEditing ? <EditActions /> : isForwarding ? <ForwardActions /> : <DefaultActions />}
      <Footer onSubmit={onSubmit} />
    </form>
  );
}
```

**Correct: composition eliminates conditionals**

```tsx
function ChannelComposer() {
  return (
    <Composer.Frame>
      <Composer.Header />
      <Composer.Input />
      <Composer.Footer>
        <Composer.Attachments />
        <Composer.Submit />
      </Composer.Footer>
    </Composer.Frame>
  );
}

function ThreadComposer({ channelId }: { channelId: string }) {
  return (
    <Composer.Frame>
      <Composer.Header />
      <Composer.Input />
      <AlsoSendToChannelField id={channelId} />
      <Composer.Footer>
        <Composer.Submit />
      </Composer.Footer>
    </Composer.Frame>
  );
}
```

---

## composition-compound-components — Compound Components with Shared Context

**Impact: HIGH (enables flexible composition without prop drilling)**

Structure complex components as compound components. Each subcomponent accesses shared state via context.

```tsx
const ComposerContext = createContext<ComposerContextValue | null>(null);

function ComposerProvider({ children, state, actions, meta }: ProviderProps) {
  return <ComposerContext value={{ state, actions, meta }}>{children}</ComposerContext>;
}

function ComposerInput() {
  const {
    state,
    actions: { update },
    meta: { inputRef },
  } = use(ComposerContext);
  return (
    <TextInput
      ref={inputRef}
      value={state.input}
      onChangeText={(text) => update((s) => ({ ...s, input: text }))}
    />
  );
}

const Composer = {
  Provider: ComposerProvider,
  Frame: ComposerFrame,
  Input: ComposerInput,
  Submit: ComposerSubmit,
};
```

---

## composition-decouple-state — Isolate State in Providers

**Impact: MEDIUM (enables swapping state implementations)**

The provider is the only place that knows how state is managed. UI components consume context, not implementations.

**Incorrect: UI coupled to state implementation**

```tsx
function ChannelComposer({ channelId }: { channelId: string }) {
  const state = useGlobalChannelState(channelId);
  return (
    <Composer.Frame>
      <Composer.Input value={state.input} />
    </Composer.Frame>
  );
}
```

**Correct: state isolated in provider**

```tsx
function ChannelProvider({ channelId, children }: Props) {
  const { state, update, submit } = useGlobalChannel(channelId);
  return (
    <Composer.Provider state={state} actions={{ update, submit }} meta={{ inputRef: useRef(null) }}>
      {children}
    </Composer.Provider>
  );
}

function ChannelComposer() {
  return (
    <Composer.Frame>
      <Composer.Input />
      <Composer.Submit />
    </Composer.Frame>
  );
}
```

Swap providers, keep the same UI.

---

## composition-context-interface — Generic Context Interfaces

**Impact: HIGH (enables dependency-injectable state)**

Define a generic interface with `state`, `actions`, and `meta`. Any provider can implement it.

```tsx
interface ComposerState {
  input: string;
  attachments: Attachment[];
  isSubmitting: boolean;
}
interface ComposerActions {
  update: (updater: (s: ComposerState) => ComposerState) => void;
  submit: () => void;
}
interface ComposerMeta {
  inputRef: React.RefObject<TextInput>;
}
interface ComposerContextValue {
  state: ComposerState;
  actions: ComposerActions;
  meta: ComposerMeta;
}
```

UI components consume the interface:

```tsx
function ComposerInput() {
  const {
    state,
    actions: { update },
    meta,
  } = use(ComposerContext);
  return (
    <TextInput
      ref={meta.inputRef}
      value={state.input}
      onChangeText={(text) => update((s) => ({ ...s, input: text }))}
    />
  );
}
```

---

## composition-lift-state — Lift State into Provider Components

**Impact: HIGH (enables state sharing outside component boundaries)**

Move state into providers so siblings can access it without prop drilling or refs.

**Incorrect: state trapped inside component**

```tsx
function ForwardMessageComposer() {
  const [state, setState] = useState(initialState);
  return (
    <Composer.Frame>
      <Composer.Input />
    </Composer.Frame>
  );
}
// Problem: ForwardButton outside cannot access submit
```

**Correct: provider wraps the whole area**

```tsx
function ForwardMessageProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState(initialState);
  const forwardMessage = useForwardMessage();
  return (
    <Composer.Provider state={state} actions={{ update: setState, submit: forwardMessage }}>
      {children}
    </Composer.Provider>
  );
}

function ForwardMessageDialog() {
  return (
    <ForwardMessageProvider>
      <Dialog>
        <ForwardMessageComposer />
        <MessagePreview />
        <DialogActions>
          <ForwardButton /> {/* Can access submit from context */}
        </DialogActions>
      </Dialog>
    </ForwardMessageProvider>
  );
}

function ForwardButton() {
  const { actions } = use(ComposerContext);
  return <Button onPress={actions.submit}>Forward</Button>;
}
```

Components that need shared state do not need to be visually nested — just within the provider.

---

## composition-explicit-variants — Explicit Variant Components

**Impact: MEDIUM (self-documenting, no hidden conditionals)**

**Incorrect: one component, many modes**

```tsx
<Composer isThread isEditing={false} channelId="abc" showAttachments showFormatting={false} />
```

**Correct: explicit variants**

```tsx
<ThreadComposer channelId="abc" />
<EditMessageComposer messageId="xyz" />
<ForwardMessageComposer messageId="123" />
```

---

## composition-children-over-render-props — Children Over Render Props

**Impact: MEDIUM (cleaner composition)**

Use `children` for static structure. Use render props only when the parent must pass data back.

**Incorrect:**

```tsx
<Composer renderHeader={() => <CustomHeader />} renderFooter={() => <Footer />} />
```

**Correct:**

```tsx
<Composer.Frame>
  <CustomHeader />
  <Composer.Input />
  <Composer.Footer>
    <SubmitButton />
  </Composer.Footer>
</Composer.Frame>
```

**Render props are appropriate when passing data:**

```tsx
<List data={items} renderItem={({ item, index }) => <Item item={item} index={index} />} />
```

---

## composition-react19-apis — React 19 API Changes

**Impact: MEDIUM (cleaner definitions and context usage)**

In React 19 (this project), `ref` is a regular prop and `use()` replaces `useContext()`.

**Incorrect: forwardRef in React 19**

```tsx
const ComposerInput = forwardRef<TextInput, Props>((props, ref) => {
  return <TextInput ref={ref} {...props} />;
});
```

**Correct: ref as regular prop**

```tsx
function ComposerInput({ ref, ...props }: Props & { ref?: React.Ref<TextInput> }) {
  return <TextInput ref={ref} {...props} />;
}
```

**Incorrect: useContext**

```tsx
const value = useContext(MyContext);
```

**Correct: use()**

```tsx
const value = use(MyContext);
```

`use()` can be called conditionally, unlike `useContext()`.
