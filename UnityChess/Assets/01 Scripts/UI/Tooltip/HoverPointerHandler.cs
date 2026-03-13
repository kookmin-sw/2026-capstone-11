using UnityEngine;
using UnityEngine.EventSystems;

public class HoverPointerHandler : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
{
    // IHoverable의 구현체인 유닛, 카드에 마우스가 올라가면 툴팁을 표시
    public void OnPointerEnter(PointerEventData eventData)
    {
        Debug.Log("툴팁 표시됨");
    }

    // 마우스가 유닛, 카드에서 벗어나면 툴팁을 숨김
    public void OnPointerExit(PointerEventData eventData)
    {
        Debug.Log("툴팁 숨김");
    }
}
