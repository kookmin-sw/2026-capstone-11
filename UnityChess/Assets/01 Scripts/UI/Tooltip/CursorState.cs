namespace entity.cursor
{
    public enum cursorState
    {
        Defalut,
        Hover,
        Select,
        Drag
    }

    public class CursorState
    {
        public cursorState CurrentState { get; set; } = cursorState.Defalut;
    }
}