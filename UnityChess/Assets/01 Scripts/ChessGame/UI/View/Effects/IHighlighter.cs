namespace ui.view.effect
{
    public enum OutlineType
    {
        None,
        Targetable,
        Selectable,
        Selected,
    }

    public interface IHightlighter
    {
        public void SetHighlight(OutlineType type);
    }
}