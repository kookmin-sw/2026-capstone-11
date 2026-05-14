using TMPro;
using UnityEngine;

public class NetworkStatus : MonoBehaviour
{
    public TMP_Text text;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        text = GetComponent<TMP_Text>();
    }

    // Update is called once per frame
    void Update()
    {
        text.text = NetworkManagerUnity.Instance.GetState();
    }
}
